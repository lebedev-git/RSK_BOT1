from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List

def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📋 Отметить присутствующих", callback_data="mark_attendance"),
        InlineKeyboardButton("🏆 Управление командами", callback_data="manage_teams"),
        InlineKeyboardButton("👑 Управление админами", callback_data="manage_admins"),
        InlineKeyboardButton("📊 Рейтинг команд", callback_data="show_rating"),
        InlineKeyboardButton("📈 Статистика участников", callback_data="show_members_statistics")
    )
    return keyboard

def get_attendance_status_keyboard(user_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✅ Присутствовал", callback_data=f"attend_present_{user_id}"),
        InlineKeyboardButton("❌ Отсутствовал", callback_data=f"attend_absent_{user_id}"),
        InlineKeyboardButton("△ Уважительная", callback_data=f"attend_excused_{user_id}")
    )
    return keyboard

def get_attendance_panel_keyboard(users: list, marked: dict = None) -> InlineKeyboardMarkup:
    if marked is None:
        marked = {}
    
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    # Добавляем три кнопки статусов сверху
    keyboard.row(
        InlineKeyboardButton("Присутствие ✅", callback_data="status_header"),
        InlineKeyboardButton("Отсутствие ❌", callback_data="status_header"),
        InlineKeyboardButton("Ув. причина ⚠️", callback_data="status_header")
    )
    
    # Добавляем разделительную линию
    keyboard.row(InlineKeyboardButton("─" * 40, callback_data="divider"))
    
    # Добавляем пользователей с кнопками статуса в одной строке
    for user in users:
        user_id = str(user['telegram_id'])
        status = marked.get(int(user_id))
        
        # Создаем строку с именем и тремя кнопками статуса
        row = [
            InlineKeyboardButton(user['username'], callback_data=f"user_{user_id}"),
            InlineKeyboardButton("⬜️" if status != "present" else "✅", callback_data=f"mark_present_{user_id}"),
            InlineKeyboardButton("⬜️" if status != "absent" else "❌", callback_data=f"mark_absent_{user_id}"),
            InlineKeyboardButton("⬜️" if status != "excused" else "⚠️", callback_data=f"mark_excused_{user_id}")
        ]
        keyboard.row(*row)
    
    # Добавляем разделительную линию
    keyboard.row(InlineKeyboardButton("─" * 40, callback_data="divider"))
    
    # Добавляем кнопки управления
    keyboard.row(
        InlineKeyboardButton("Завершить отметку ✅", callback_data="finish_attendance"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
    )
    
    return keyboard

def get_manage_admins_keyboard(users: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    for user in users:
        admin_status = "👑" if user["is_admin"] else "⬜️"
        keyboard.row(
            InlineKeyboardButton(f"{user['username']}", callback_data=f"user_info_{user['telegram_id']}"),
            InlineKeyboardButton(admin_status, callback_data=f"toggle_admin_{user['telegram_id']}")
        )
    
    keyboard.row(InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin"))
    return keyboard

def get_team_management_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Создать команду", callback_data="create_team"),
        InlineKeyboardButton("Редактировать команды", callback_data="edit_teams"),
        InlineKeyboardButton("Управление баллами", callback_data="manage_points"),
        InlineKeyboardButton("История начислений", callback_data="points_history"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
    )
    return keyboard

def get_teams_edit_keyboard(teams: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    for team in teams:
        keyboard.add(
            InlineKeyboardButton(f"✏️ {team['name']}", callback_data=f"edit_team_{team['id']}")
        )
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_team_management"))
    return keyboard

def get_team_edit_keyboard(team: dict, members: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Добавляем текущих участников с возможностью удаления
    for member in members:
        keyboard.add(
            InlineKeyboardButton(
                f"❌ {member['username']}", 
                callback_data=f"remove_member_{team['id']}_{member['telegram_id']}"
            )
        )
    
    keyboard.add(
        InlineKeyboardButton("➕ Добавить участника", callback_data=f"add_member_{team['id']}"),
        InlineKeyboardButton("🗑 Удалить команду", callback_data=f"delete_team_{team['id']}"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_teams_edit")
    )
    return keyboard

def get_members_selection_keyboard(users: list, selected: List[int] = None) -> InlineKeyboardMarkup:
    if selected is None:
        selected = []
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for user in users:
        mark = "✅" if user["telegram_id"] in selected else "⬜️"
        keyboard.add(
            InlineKeyboardButton(
                f"{mark} {user['username']}", 
                callback_data=f"select_member_{user['telegram_id']}"
            )
        )
    
    keyboard.row(
        InlineKeyboardButton("Подтвердить ✅", callback_data="confirm_members"),
        InlineKeyboardButton("Отмена ❌", callback_data="cancel_selection")
    )
    return keyboard

def get_teams_points_keyboard(teams: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    for team in teams:
        keyboard.add(
            InlineKeyboardButton(
                f"{team['name']} ({team['points']} баллов)", 
                callback_data=f"manage_team_points_{team['id']}"
            )
        )
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_team_management"))
    return keyboard 