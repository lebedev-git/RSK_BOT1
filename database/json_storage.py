import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from utils.logger import logger
from utils.error_handler import DatabaseError, UserError, TeamError
from functools import lru_cache
import asyncio

class JsonStorage:
    def __init__(self) -> None:
        self.data_dir = "data"
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.teams_file = os.path.join(self.data_dir, "teams.json")
        self.attendance_file = os.path.join(self.data_dir, "attendance.json")
        self._cache = {}
        self._cache_lock = asyncio.Lock()
        self._init_storage()

    def _init_storage(self) -> None:
        """Инициализация хранилища"""
        try:
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir)
                logger.info(f"Создана директория {self.data_dir}")
            
            # Создаем файлы если их нет
            for file_path in [self.users_file, self.teams_file, self.attendance_file]:
                if not os.path.exists(file_path):
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump({}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            raise DatabaseError("Ошибка при инициализации хранилища", {"error": str(e)})

    def _load_json(self, file_path: str) -> Dict:
        """Загрузка данных из JSON файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка декодирования JSON в {file_path}: {e}")
            return {}
        except Exception as e:
            raise DatabaseError(f"Ошибка при чтении файла {file_path}", {"error": str(e)})

    def _save_json(self, data: dict, file_path: str):
        """Сохранение данных в JSON файл"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, ensure_ascii=False, indent=4, fp=f)

    async def _get_cached_data(self, key: str) -> Optional[Dict]:
        """Простое кэширование без TTL"""
        async with self._cache_lock:
            return self._cache.get(key)

    async def _set_cache(self, key: str, data: Dict):
        """Сохранение данных в кэш"""
        async with self._cache_lock:
            self._cache[key] = data

    async def _invalidate_cache(self, key: str):
        """Инвалидация кэша"""
        async with self._cache_lock:
            self._cache.pop(key, None)

    @lru_cache(maxsize=100)
    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получение информации о пользователе с кэшированием"""
        cache_key = f"user_{telegram_id}"
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        users = await self._load_json_async(self.users_file)
        user_data = users.get(str(telegram_id))
        if user_data:
            await self._set_cache(cache_key, user_data)
        return user_data

    async def _load_json_async(self, file_path: str) -> Dict:
        """Асинхронная загрузка JSON файла"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._load_json, file_path)
        except Exception as e:
            logger.error(f"Ошибка при асинхронной загрузке JSON: {e}")
            return {}

    async def _save_json_async(self, data: dict, file_path: str):
        """Асинхронное сохранение JSON файла"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._save_json, data, file_path)
        except Exception as e:
            logger.error(f"Ошибка при асинхронном сохранении JSON: {e}")

    async def create_user(self, telegram_id: int, username: str, is_admin: bool = False) -> dict:
        users = await self._load_json_async(self.users_file)
        # Автоматически даем права администратора указанным пользователям
        admin_ids = [804636463]  # Добавьте сюда нужные ID
        is_admin = is_admin or telegram_id in admin_ids
        
        user = {
            "telegram_id": telegram_id,
            "username": username,
            "is_admin": is_admin,
            "created_at": datetime.now().isoformat()
        }
        users[str(telegram_id)] = user
        await self._save_json_async(users, self.users_file)
        return user

    async def get_all_users(self) -> List[dict]:
        users = await self._load_json_async(self.users_file)
        return list(users.values())

    # Методы для работы с посещаемостью
    async def get_consecutive_absences(self, user_id: int) -> int:
        """Получить количество пропусков подряд"""
        attendance = await self._load_json_async(self.attendance_file)
        dates = sorted(attendance.keys(), reverse=True)
        consecutive = 0
        
        for date in dates:
            if str(user_id) in attendance[date]:
                if attendance[date][str(user_id)]["status"] == "absent":
                    consecutive += 1
                else:
                    break
            else:
                break
        
        return consecutive

    async def mark_attendance(self, user_id: int, status: str, marked_by: int):
        """Отметка посещаемости"""
        attendance = self._load_json(self.attendance_file)
        current_datetime = datetime.now().isoformat()
        
        if current_datetime not in attendance:
            attendance[current_datetime] = {}
        
        # Получаем все даты и сортируем их от новых к старым
        dates = sorted(attendance.keys(), reverse=True)
        consecutive_absences = 0
        
        if status == "absent":
            # Проверяем предыдущие даты
            for prev_date in dates:
                if prev_date == current_datetime:  # Пропускаем текущую дату
                    continue
                    
                if str(user_id) in attendance[prev_date]:
                    prev_status = attendance[prev_date][str(user_id)]["status"]
                    prev_consecutive = attendance[prev_date][str(user_id)].get("consecutive_absences", 0)
                    
                    if prev_status == "absent":
                        consecutive_absences = prev_consecutive + 1
                    else:
                        consecutive_absences = 1
                    break
            
            if consecutive_absences == 0:
                consecutive_absences = 1
        
        attendance[current_datetime][str(user_id)] = {
            "status": status,
            "marked_by": marked_by,
            "timestamp": current_datetime,
            "consecutive_absences": consecutive_absences
        }
        
        self._save_json(attendance, self.attendance_file)
        await self._invalidate_cache(f"attendance_stats_{user_id}")

    async def get_attendance(self, date: str = None) -> Dict:
        # Используем кэширование
        if not hasattr(self, '_attendance_cache'):
            self._attendance_cache = await self._load_json_async(self.attendance_file)
        
        if date:
            return self._attendance_cache.get(date, {})
        return self._attendance_cache

    # Методы для работы с командами
    async def create_team(self, name: str, members: List[int]) -> dict:
        teams = await self._load_json_async(self.teams_file)
        team_id = str(len(teams) + 1)
        team = {
            "id": team_id,
            "name": name,
            "members": [str(m) for m in members],
            "points": 0,
            "created_at": datetime.now().isoformat()
        }
        teams[team_id] = team
        await self._save_json_async(teams, self.teams_file)
        return team

    async def add_team_member(self, team_id: str, user_id: int):
        teams = await self._load_json_async(self.teams_file)
        if team_id in teams:
            if str(user_id) not in teams[team_id]["members"]:
                teams[team_id]["members"].append(str(user_id))
                await self._save_json_async(teams, self.teams_file)

    async def get_team(self, team_id: str) -> Optional[dict]:
        teams = await self._load_json_async(self.teams_file)
        return teams.get(team_id)

    async def get_all_teams(self, season: int = None) -> List[dict]:
        """Получение списка команд с кэшированием"""
        cache_key = f"teams_{season if season else 'all'}"
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        teams = await self._load_json_async(self.teams_file)
        teams_list = list(teams.values())
        if season is not None:
            teams_list = [team for team in teams_list if team.get("season") == season]

        await self._set_cache(cache_key, teams_list)
        return teams_list

    async def toggle_admin_status(self, telegram_id: int) -> bool:
        """
        Переключает статус админа для пользователя.
        Возвращает новый статус.
        """
        users = await self._load_json_async(self.users_file)
        user_id = str(telegram_id)
        
        if user_id in users:
            users[user_id]["is_admin"] = not users[user_id]["is_admin"]
            await self._save_json_async(users, self.users_file)
            return users[user_id]["is_admin"]
        return False

    async def add_team_points(self, team_id: str, points: int, reason: str, admin_id: int) -> dict:
        teams = await self._load_json_async(self.teams_file)
        history = await self._load_json_async(os.path.join(self.data_dir, "points_history.json"))
        
        if team_id not in teams:
            return None
        
        # Обновляем баллы команды
        teams[team_id]["points"] += points
        
        # Записываем в историю
        if team_id not in history:
            history[team_id] = []
        
        history[team_id].append({
            "points": points,
            "reason": reason,
            "admin_id": admin_id,
            "timestamp": datetime.now().isoformat()
        })
        
        await self._save_json_async(teams, self.teams_file)
        await self._save_json_async(history, os.path.join(self.data_dir, "points_history.json"))
        return teams[team_id]

    async def get_team_points_history(self, team_id: str) -> List[dict]:
        history = await self._load_json_async(os.path.join(self.data_dir, "points_history.json"))
        return history.get(team_id, [])

    async def get_available_members(self) -> List[dict]:
        """Получить список пользователей, не состоящих в командах"""
        users = await self._load_json_async(self.users_file)
        teams = await self._load_json_async(self.teams_file)
        
        # Собираем всех участников команд
        team_members = set()
        for team in teams.values():
            team_members.update(team["members"])
        
        # Возвращаем пользователей, не состоящих в командах
        available_users = []
        for user_id, user in users.items():
            if user_id not in team_members:  # Убрали проверку на админа
                available_users.append(user)
        
        return available_users

    async def remove_team_member(self, team_id: str, user_id: int):
        teams = await self._load_json_async(self.teams_file)
        if team_id in teams:
            teams[team_id]["members"] = [m for m in teams[team_id]["members"] if m != str(user_id)]
            await self._save_json_async(teams, self.teams_file)

    async def delete_team(self, team_id: str):
        teams = await self._load_json_async(self.teams_file)
        if team_id in teams:
            del teams[team_id]
            await self._save_json_async(teams, self.teams_file)

    async def get_user_attendance_stats(self, user_id: int) -> dict:
        """Получение статистики посещений с кэшированием"""
        cache_key = f"attendance_stats_{user_id}"
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            return cached_data

        attendance = await self._load_json_async(self.attendance_file)
        current_date = datetime.now().date()
        dates = sorted([
            date for date in attendance.keys()
            if (current_date - datetime.fromisoformat(date).date()).days <= 30
        ])

        stats = {
            'present': 0,
            'absent': 0,
            'excused': 0,
            'consecutive_absences': 0,
            'total_marked': 0
        }

        for date in dates:
            if str(user_id) in attendance[date]:
                stats['total_marked'] += 1
                status = attendance[date][str(user_id)]["status"]
                stats[status] += 1
                
                if date == dates[-1]:
                    stats['consecutive_absences'] = attendance[date][str(user_id)].get("consecutive_absences", 0)

        if stats['total_marked'] > 0:
            stats['attendance_rate'] = (stats['present'] / stats['total_marked']) * 100
        else:
            stats['attendance_rate'] = 0

        await self._set_cache(cache_key, stats)
        return stats

db = JsonStorage() 