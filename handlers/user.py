from aiogram import types, Dispatcher
from aiogram.dispatcher import FSMContext
from database.json_storage import db
from utils.keyboards import get_user_keyboard
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def user_menu(message: types.Message, state: FSMContext):
    """Обработчик команды /menu для всех пользователей"""
    user = await db.get_user(message.from_user.id)
    if not user:
        return await message.answer("❌ Вы не зарегистрированы в системе.")
    
    # Получаем статистику пользователя
    stats = await db.get_user_attendance_stats(message.from_user.id)
    
    text = (
        f"👤 Моя статистика посещений\n"
        f"{'─' * 30}\n\n"
        f"📅 Всего отметок: {stats['total_marked']}\n\n"
        f"✅ Присутствовал: {stats['present']} ({(stats['present']/stats['total_marked']*100):.1f}%)\n"
        f"❌ Отсутствовал: {stats['absent']} ({(stats['absent']/stats['total_marked']*100):.1f}%)"
    )
    
    # Добавляем информацию о пропусках подряд
    if stats['consecutive_absences'] > 1:
        text += f" ⚠️ {stats['consecutive_absences']} раз подряд"
    
    text += (
        f"\n⚠️ По ув. причине: {stats['excused']} ({(stats['excused']/stats['total_marked']*100):.1f}%)\n\n"
        f"📈 Общая посещаемость: {stats['attendance_rate']:.1f}%\n"
    )
    
    # Добавляем оценку посещаемости
    if stats['attendance_rate'] >= 90:
        text += "\n🌟 Отличная посещаемость!"
    elif stats['attendance_rate'] >= 75:
        text += "\n👍 Хорошая посещаемость"
    elif stats['attendance_rate'] >= 50:
        text += "\n⚠️ Средняя посещаемость"
    else:
        text += "\n❗️ Низкая посещаемость"
    
    keyboard = get_user_keyboard()
    await message.answer(text, reply_markup=keyboard)

async def show_teams_rating(callback_query: types.CallbackQuery):
    """Показать рейтинг команд"""
    teams = await db.get_all_teams()
    teams_sorted = sorted(teams, key=lambda x: x['points'], reverse=True)
    
    text = "📊 РЕЙТИНГ КОМАНД\n\n"
    
    for i, team in enumerate(teams_sorted, 1):
        prefix = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{prefix} {team['name']}\n"
        text += f"└ {team['points']} баллов\n"
        members = []
        for member_id in team['members']:
            user = await db.get_user(int(member_id))
            if user:
                members.append(user['username'])
        text += f"👥 Участники: {', '.join(members)}\n\n"
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu"))
    await callback_query.message.edit_text(text, reply_markup=keyboard)

def format_user_stats(stats: dict, user: dict) -> str:
    """Форматирование статистики пользователя"""
    text = (
        f"👤 Моя статистика посещений\n"
        f"{'─' * 30}\n\n"
        f"📅 Всего отметок: {stats['total_marked']}\n\n"
        f"✅ Присутствовал: {stats['present']} ({(stats['present']/stats['total_marked']*100):.1f}%)\n"
        f"❌ Отсутствовал: {stats['absent']} ({(stats['absent']/stats['total_marked']*100):.1f}%)"
    )
    
    if stats['consecutive_absences'] > 1:
        text += f" ⚠️ {stats['consecutive_absences']} раз подряд"
    
    text += (
        f"\n⚠️ По ув. причине: {stats['excused']} ({(stats['excused']/stats['total_marked']*100):.1f}%)\n\n"
        f"📈 Общая посещаемость: {stats['attendance_rate']:.1f}%\n"
    )
    
    if stats['attendance_rate'] >= 90:
        text += "\n🌟 Отличная посещаемость!"
    elif stats['attendance_rate'] >= 75:
        text += "\n👍 Хорошая посещаемость"
    elif stats['attendance_rate'] >= 50:
        text += "\n⚠️ Средняя посещаемость"
    else:
        text += "\n❗️ Низкая посещаемость"
    
    return text

async def back_to_menu(callback_query: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    user = await db.get_user(callback_query.from_user.id)
    if not user:
        return await callback_query.answer("❌ Ошибка: пользователь не найден")
    
    stats = await db.get_user_attendance_stats(user['telegram_id'])
    text = format_user_stats(stats, user)
    await callback_query.message.edit_text(text, reply_markup=get_user_keyboard())

def register_handlers(dp: Dispatcher):
    dp.register_message_handler(user_menu, commands=["menu"], state="*")
    dp.register_callback_query_handler(show_teams_rating, text="show_teams_rating", state="*")
    dp.register_callback_query_handler(back_to_menu, text="back_to_menu", state="*") 