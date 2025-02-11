from aiogram import Dispatcher, types
from database.json_storage import db
from datetime import datetime

def get_current_season() -> int:
    """Получение текущего сезона (например, номер текущего месяца)"""
    return datetime.now().month

async def show_rating(message: types.Message):
    # Получаем все команды текущего сезона
    teams = await db.get_all_teams(season=get_current_season())
    
    if not teams:
        return await message.answer("В текущем сезоне нет активных команд.")
    
    rating_text = "📊 Текущий рейтинг команд:\n\n"
    
    for team in teams:
        # Получаем всех членов команды
        members = team["members"]
        total_score = 0
        
        # Проверяем посещаемость каждого члена команды
        attendance = await db.get_attendance(datetime.now().date().isoformat())
        all_present = True
        
        for member_id in members:
            member_attendance = attendance.get(member_id, {})
            if member_attendance.get("status") == "present":
                total_score += 2
            elif member_attendance.get("status") == "absent":
                all_present = False
                total_score -= 2
        
        # Если все присутствовали, добавляем бонус
        if all_present and members:
            total_score += 2
        
        rating_text += f"Команда {team['name']}: {total_score} баллов\n"
    
    await message.answer(rating_text)

def register_handlers(dp: Dispatcher):
    dp.register_message_handler(show_rating, commands=["rating"]) 