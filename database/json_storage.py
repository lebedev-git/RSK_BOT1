import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Union
from utils.logger import logger
from utils.error_handler import DatabaseError, UserError, TeamError

class JsonStorage:
    def __init__(self) -> None:
        self.data_dir = "data"
        self.users_file = os.path.join(self.data_dir, "users.json")
        self.teams_file = os.path.join(self.data_dir, "teams.json")
        self.attendance_file = os.path.join(self.data_dir, "attendance.json")
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

    # Методы для работы с пользователями
    async def get_user(self, telegram_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        try:
            users = self._load_json(self.users_file)
            return users.get(str(telegram_id))
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя {telegram_id}: {e}")
            return None

    async def create_user(self, telegram_id: int, username: str, is_admin: bool = False) -> dict:
        users = self._load_json(self.users_file)
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
        self._save_json(users, self.users_file)
        return user

    async def get_all_users(self) -> List[dict]:
        users = self._load_json(self.users_file)
        return list(users.values())

    # Методы для работы с посещаемостью
    async def get_consecutive_absences(self, user_id: int) -> int:
        """Получить количество пропусков подряд"""
        attendance = self._load_json(self.attendance_file)
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
        attendance = self._load_json(self.attendance_file)
        current_datetime = datetime.now().isoformat()  # Используем полную дату со временем
        
        if current_datetime not in attendance:
            attendance[current_datetime] = {}
        
        # Получаем все даты и сортируем их от новых к старым
        dates = sorted(attendance.keys(), reverse=True)
        consecutive_absences = 0
        
        print(f"\nProcessing attendance for user {user_id}")
        print(f"Current status: {status}")
        print(f"Current datetime: {current_datetime}")
        
        if status == "absent":
            # Проверяем предыдущие отметки
            for prev_date in dates:
                if prev_date == current_datetime:  # Пропускаем текущую отметку
                    continue
                    
                if str(user_id) in attendance[prev_date]:
                    prev_status = attendance[prev_date][str(user_id)]["status"]
                    prev_consecutive = attendance[prev_date][str(user_id)].get("consecutive_absences", 0)
                    
                    print(f"Found previous record on {prev_date}:")
                    print(f"- Status: {prev_status}")
                    print(f"- Consecutive absences: {prev_consecutive}")
                    
                    if prev_status == "absent":
                        consecutive_absences = prev_consecutive + 1
                        print(f"Previous was absent, increasing to: {consecutive_absences}")
                    else:
                        consecutive_absences = 1
                        print(f"Previous was not absent, setting to: {consecutive_absences}")
                    break
            
            # Если не нашли предыдущих отметок
            if consecutive_absences == 0:
                consecutive_absences = 1
                print("No previous records found, setting to: 1")
        
        print(f"Final consecutive absences: {consecutive_absences}")
        
        # Очищаем кэш перед сохранением
        if hasattr(self, '_attendance_cache'):
            delattr(self, '_attendance_cache')
        
        attendance[current_datetime][str(user_id)] = {
            "status": status,
            "marked_by": marked_by,
            "timestamp": current_datetime,
            "consecutive_absences": consecutive_absences
        }
        
        self._save_json(attendance, self.attendance_file)

    async def get_attendance(self, date: str = None) -> Dict:
        # Используем кэширование
        if not hasattr(self, '_attendance_cache'):
            self._attendance_cache = self._load_json(self.attendance_file)
        
        if date:
            return self._attendance_cache.get(date, {})
        return self._attendance_cache

    # Методы для работы с командами
    async def create_team(self, name: str, members: List[int]) -> dict:
        teams = self._load_json(self.teams_file)
        team_id = str(len(teams) + 1)
        team = {
            "id": team_id,
            "name": name,
            "members": [str(m) for m in members],
            "points": 0,
            "created_at": datetime.now().isoformat()
        }
        teams[team_id] = team
        self._save_json(teams, self.teams_file)
        return team

    async def add_team_member(self, team_id: str, user_id: int):
        teams = self._load_json(self.teams_file)
        if team_id in teams:
            if str(user_id) not in teams[team_id]["members"]:
                teams[team_id]["members"].append(str(user_id))
                self._save_json(teams, self.teams_file)

    async def get_team(self, team_id: str) -> Optional[dict]:
        teams = self._load_json(self.teams_file)
        return teams.get(team_id)

    async def get_all_teams(self, season: int = None) -> List[dict]:
        teams = self._load_json(self.teams_file)
        if season is not None:
            return [team for team in teams.values() if team["season"] == season]
        return list(teams.values())

    async def toggle_admin_status(self, telegram_id: int) -> bool:
        """
        Переключает статус админа для пользователя.
        Возвращает новый статус.
        """
        users = self._load_json(self.users_file)
        user_id = str(telegram_id)
        
        if user_id in users:
            users[user_id]["is_admin"] = not users[user_id]["is_admin"]
            self._save_json(users, self.users_file)
            return users[user_id]["is_admin"]
        return False

    async def add_team_points(self, team_id: str, points: int, reason: str, admin_id: int) -> dict:
        teams = self._load_json(self.teams_file)
        history = self._load_json(os.path.join(self.data_dir, "points_history.json"))
        
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
        
        self._save_json(teams, self.teams_file)
        self._save_json(history, os.path.join(self.data_dir, "points_history.json"))
        return teams[team_id]

    async def get_team_points_history(self, team_id: str) -> List[dict]:
        history = self._load_json(os.path.join(self.data_dir, "points_history.json"))
        return history.get(team_id, [])

    async def get_available_members(self) -> List[dict]:
        """Получить список пользователей, не состоящих в командах"""
        users = self._load_json(self.users_file)
        teams = self._load_json(self.teams_file)
        
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
        teams = self._load_json(self.teams_file)
        if team_id in teams:
            teams[team_id]["members"] = [m for m in teams[team_id]["members"] if m != str(user_id)]
            self._save_json(teams, self.teams_file)

    async def delete_team(self, team_id: str):
        teams = self._load_json(self.teams_file)
        if team_id in teams:
            del teams[team_id]
            self._save_json(teams, self.teams_file)

    async def get_user_attendance_stats(self, user_id: int) -> dict:
        """Получить статистику посещений пользователя за последние 30 дней"""
        attendance = self._load_json(self.attendance_file)
        
        # Получаем даты за последние 30 дней
        current_date = datetime.now().date()
        dates = sorted([
            date for date in attendance.keys()
            if (current_date - datetime.fromisoformat(date).date()).days <= 30
        ])
        
        print(f"Getting stats for user {user_id}")
        print(f"Found dates: {dates}")
        
        stats = {
            'present': 0,
            'absent': 0,
            'excused': 0,
            'consecutive_absences': 0,
            'total_marked': 0
        }
        
        # Подсчитываем статистику
        for date in dates:
            if str(user_id) in attendance[date]:
                stats['total_marked'] += 1
                status = attendance[date][str(user_id)]["status"]
                stats[status] += 1
                
                # Берем последнее значение consecutive_absences
                if date == dates[-1]:
                    stats['consecutive_absences'] = attendance[date][str(user_id)].get("consecutive_absences", 0)
        
        # Считаем процент посещаемости
        if stats['total_marked'] > 0:
            stats['attendance_rate'] = (stats['present'] / stats['total_marked']) * 100
        else:
            stats['attendance_rate'] = 0
        
        print(f"Final stats: {stats}")
        return stats

db = JsonStorage() 