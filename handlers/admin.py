from aiogram import Dispatcher, types
from aiogram.dispatcher.filters import Command
from database.json_storage import db
from utils.keyboards import (
    get_admin_keyboard, 
    get_attendance_panel_keyboard, 
    get_manage_admins_keyboard, 
    get_team_management_keyboard, 
    get_members_selection_keyboard, 
    get_teams_points_keyboard,
    get_teams_edit_keyboard,
    get_team_edit_keyboard
)
from config import config
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import pandas as pd
from io import BytesIO

class TeamCreation(StatesGroup):
    waiting_for_name = State()

class TeamMemberAdd(StatesGroup):
    waiting_for_team = State()
    waiting_for_username = State()

class AttendanceMarking(StatesGroup):
    marking = State()

class AdminManagement(StatesGroup):
    managing = State()

class TeamManagement(StatesGroup):
    selecting_members = State()
    entering_name = State()
    managing_points = State()
    entering_points = State()
    entering_reason = State()

class TeamEditing(StatesGroup):
    selecting_team = State()
    adding_member = State()
    confirming_delete = State()

async def admin_panel(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_admin"]:
        return await message.answer("❌ У вас нет прав администратора.")
    
    await state.finish()
    
    text = "👑 ПАНЕЛЬ АДМИНИСТРАТОРА\n\n"
    text += "Выберите действие из меню ниже:\n"
    text += "📋 Отметка присутствия - отметить присутствующих\n"
    text += "🏆 Управление командами - работа с командами\n"
    text += "👥 Управление админами - назначение администраторов\n"
    text += "📊 Рейтинг - просмотр и публикация рейтинга\n"
    text += "📈 Статистика участников - личная статистика"
    
    await message.answer(text, reply_markup=get_admin_keyboard())

async def start_attendance_marking(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем всех пользователей (включая админов)
    users = await db.get_all_users()
    
    # Сохраняем список пользователей в состояние
    await state.update_data(users=users, marked={})
    
    text = "📋 Отметка присутствия\n\n"
    text += "Нажмите на соответствующий значок, чтобы отметить статус:\n"
    text += "✅ - присутствует\n"
    text += "❌ - отсутствует\n"
    text += "⚠️ - уважительная причина\n\n"
    text += "После отметки всех участников нажмите 'Завершить отметку'"
    
    keyboard = get_attendance_panel_keyboard(users)
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await AttendanceMarking.marking.set()

async def handle_attendance_mark(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        users = data.get('users', [])
        marked = data.get('marked', {})
        
        if callback_query.data.startswith("mark_"):
            _, status, user_id = callback_query.data.split('_')
            user_id = int(user_id)
            marked[user_id] = status
            await state.update_data(marked=marked)
            
            # Используем только edit_reply_markup вместо edit_text
            await callback_query.message.edit_reply_markup(
                reply_markup=get_attendance_panel_keyboard(users, marked)
            )
            await callback_query.answer()
            return
        
        elif callback_query.data == "finish_attendance":
            # Проверяем, все ли отмечены
            if len(marked) < len(users):
                await callback_query.answer("Пожалуйста, отметьте всех участников!")
                return
            
            # Получаем текущую посещаемость
            attendance = await db.get_attendance()
            current_date = datetime.now().date().isoformat()
            
            # Группируем пользователей по статусам
            present_users = []
            absent_users = []
            excused_users = []
            
            for user_id, status in marked.items():
                # Сохраняем в базу
                await db.mark_attendance(
                    user_id=user_id,
                    status=status,
                    marked_by=callback_query.from_user.id
                )
                
                # Находим пользователя
                user = next((u for u in users if u["telegram_id"] == user_id), None)
                if user:
                    if status == "present":
                        present_users.append(user["username"])
                    elif status == "absent":
                        absent_users.append(user)  # Сохраняем весь объект пользователя
                    elif status == "excused":
                        excused_users.append(user["username"])
            
            # Получаем все команды и начисляем баллы
            teams = await db.get_all_teams()
            for team in teams:
                team_attendance = {"present": 0, "absent": 0, "excused": 0}
                
                for member_id in team['members']:
                    member_status = marked.get(int(member_id))
                    if member_status in ["present", "excused"]:
                        team_attendance["present"] += 1
                    elif member_status == "absent":
                        team_attendance["absent"] += 1
                
                # Если хотя бы один отсутствовал - снимаем баллы
                if team_attendance["absent"] > 0:
                    await db.add_team_points(
                        team_id=team['id'],
                        points=-2,
                        reason="Автоматическое снятие баллов за пропуск занятия",
                        admin_id=callback_query.from_user.id
                    )
            
            # Формируем текст с результатами
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
            result_text = (
                f"📋 ОТЧЕТ О ПОСЕЩАЕМОСТИ\n"
                f"{'─' * 30}\n"
                f"📅 {current_time}\n\n"
                
                "✅ ПРИСУТСТВОВАЛИ:\n"
                f"{''.join(f'└ {user}\n' for user in present_users) if present_users else '└ (нет)\n'}\n"
                
                "❌ ОТСУТСТВОВАЛИ:\n"
                f"{''.join(f'└ {user['username']}{' ⚠️ ' + str(attendance[current_date][str(user['telegram_id'])]['consecutive_absences']) + ' раз подряд' if attendance[current_date][str(user['telegram_id'])]['consecutive_absences'] > 1 else ''}\n' for user in absent_users) if absent_users else '└ (нет)\n'}\n"
                
                "⚠️ ПО УВАЖИТЕЛЬНОЙ ПРИЧИНЕ:\n"
                f"{''.join(f'└ {user}\n' for user in excused_users) if excused_users else '└ (нет)\n'}"
            )
            
            # Отправляем результаты в групповой чат
            await callback_query.bot.send_message(config.GROUP_CHAT_ID, result_text)
            
            # Возвращаемся в админ-панель
            await callback_query.message.edit_text(
                "Отметка присутствия завершена!",
                reply_markup=get_admin_keyboard()
            )
            await state.finish()
        
        elif callback_query.data == "back_to_admin":
            await callback_query.message.edit_text(
                "Панель администратора:",
                reply_markup=get_admin_keyboard()
            )
            await state.finish()
        
        await callback_query.answer()
    except Exception as e:
        print(f"Error in handle_attendance_mark: {e}")
        await callback_query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)

async def cmd_create_team(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_admin"]:
        return await message.answer("У вас нет прав администратора.")
    
    await TeamCreation.waiting_for_name.set()
    await message.answer("Введите название новой команды:")

async def process_team_name(message: types.Message, state: FSMContext):
    team_name = message.text
    current_season = datetime.now().month
    
    team = await db.create_team(name=team_name, season=current_season)
    await message.answer(f"Команда '{team_name}' успешно создана!")
    await state.finish()

async def cmd_add_member(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user or not user["is_admin"]:
        return await message.answer("У вас нет прав администратора.")
    
    teams = await db.get_all_teams(season=datetime.now().month)
    if not teams:
        return await message.answer("Нет доступных команд. Сначала создайте команду.")
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for team in teams:
        keyboard.add(InlineKeyboardButton(
            text=team["name"],
            callback_data=f"select_team_{team['id']}"
        ))
    
    await TeamMemberAdd.waiting_for_team.set()
    await message.answer("Выберите команду для добавления участника:", reply_markup=keyboard)

async def process_team_selection(callback: types.CallbackQuery, state: FSMContext):
    team_id = callback.data.split('_')[2]
    await state.update_data(team_id=team_id)
    await TeamMemberAdd.waiting_for_username.set()
    await callback.message.answer("Введите username участника (без @):")
    await callback.answer()

async def process_member_username(message: types.Message, state: FSMContext):
    username = message.text.strip('@')
    data = await state.get_data()
    team_id = data['team_id']
    
    # Проверяем, существует ли пользователь
    users = await db.get_all_users()
    user = next((u for u in users if u["username"] == username), None)
    
    if not user:
        await message.answer("Пользователь не найден. Убедитесь, что он уже использовал бота (/start)")
        await state.finish()
        return
    
    await db.add_team_member(team_id, user["telegram_id"])
    team = await db.get_team(team_id)
    await message.answer(f"Участник @{username} добавлен в команду {team['name']}!")
    await state.finish()

async def manage_admins(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "back_to_admin":
        await callback_query.message.edit_text(
            "Панель администратора:",
            reply_markup=get_admin_keyboard()
        )
        await state.finish()
        return

    # Проверяем, является ли пользователь Лебедевым Андреем
    user = await db.get_user(callback_query.from_user.id)
    if not user or user["username"] != "Лебедев Андрей":
        await callback_query.answer("Только Лебедев Андрей может управлять админами!")
        return
    
    # Получаем всех пользователей
    users = await db.get_all_users()
    
    text = "👑 Управление правами администраторов\n\n"
    text += "Нажмите на значок справа от пользователя, чтобы изменить его права:\n"
    text += "👑 - администратор\n"
    text += "⬜️ - обычный пользователь"
    
    keyboard = get_manage_admins_keyboard(users)
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await AdminManagement.managing.set()

async def toggle_admin_rights(callback_query: types.CallbackQuery, state: FSMContext):
    # Проверяем, является ли пользователь Лебедевым Андреем
    user = await db.get_user(callback_query.from_user.id)
    if not user or user["username"] != "Лебедев Андрей":
        await callback_query.answer("Только Лебедев Андрей может управлять админами!")
        return

    try:
        # Получаем ID пользователя из callback_data
        target_id = int(callback_query.data.replace("toggle_admin_", ""))
        
        # Получаем информацию о целевом пользователе
        target_user = await db.get_user(target_id)
        if not target_user:
            await callback_query.answer("Пользователь не найден!")
            return
        
        # Переключаем статус админа
        new_status = await db.toggle_admin_status(target_id)
        
        # Получаем обновленный список пользователей
        users = await db.get_all_users()
        
        # Обновляем клавиатуру
        keyboard = get_manage_admins_keyboard(users)
        await callback_query.message.edit_reply_markup(reply_markup=keyboard)
        
        # Отправляем уведомление
        status_text = "назначен администратором" if new_status else "снят с прав администратора"
        await callback_query.answer(
            f"Пользователь {target_user['username']} {status_text}",
            show_alert=True
        )
    except Exception as e:
        print(f"Error in toggle_admin_rights: {e}")
        await callback_query.answer("Произошла ошибка при изменении прав", show_alert=True)

async def team_management(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "back_to_admin":
        await callback_query.message.edit_text(
            "Панель администратора:",
            reply_markup=get_admin_keyboard()
        )
        await state.finish()
        return
    elif callback_query.data == "back_to_team_management":
        keyboard = get_team_management_keyboard()
        await callback_query.message.edit_text(
            "🏆 Управление командами\n\n"
            "Выберите действие:",
            reply_markup=keyboard
        )
        return
    elif callback_query.data == "back_to_teams_list":
        teams = await db.get_all_teams()
        keyboard = get_teams_edit_keyboard(teams)
        await callback_query.message.edit_text(
            "✏️ Редактирование команд\n\n"
            "Выберите команду для редактирования:",
            reply_markup=keyboard
        )
        return

    keyboard = get_team_management_keyboard()
    await callback_query.message.edit_text(
        "🏆 Управление командами\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )
    await callback_query.answer()

async def start_team_creation(callback_query: types.CallbackQuery, state: FSMContext):
    # Получаем доступных участников
    available_users = await db.get_available_members()
    if len(available_users) < 2:
        await callback_query.answer("Недостаточно свободных участников для создания команды!", show_alert=True)
        return

    keyboard = get_members_selection_keyboard(available_users)
    await callback_query.message.edit_text(
        "👥 Создание новой команды\n\n"
        "Выберите участников команды (минимум 2):",
        reply_markup=keyboard
    )
    await TeamManagement.selecting_members.set()
    await state.update_data(selected_members=[])
    await callback_query.answer()

async def toggle_member_selection(callback_query: types.CallbackQuery, state: FSMContext):
    member_id = int(callback_query.data.replace("select_member_", ""))
    data = await state.get_data()
    selected_members = data.get('selected_members', [])

    if member_id in selected_members:
        selected_members.remove(member_id)
    else:
        selected_members.append(member_id)

    await state.update_data(selected_members=selected_members)
    available_users = await db.get_available_members()
    keyboard = get_members_selection_keyboard(available_users, selected_members)
    
    await callback_query.message.edit_reply_markup(reply_markup=keyboard)
    await callback_query.answer()

async def confirm_member_selection(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_members = data.get('selected_members', [])

    if len(selected_members) < 2:
        await callback_query.answer("Выберите минимум 2 участника!", show_alert=True)
        return

    await callback_query.message.edit_text("Введите название для команды:")
    await TeamManagement.entering_name.set()
    await callback_query.answer()

async def process_team_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    selected_members = data.get('selected_members', [])
    
    # Создаем команду
    team = await db.create_team(name=message.text, members=selected_members)
    
    # Получаем имена участников
    members_names = []
    for member_id in selected_members:
        user = await db.get_user(member_id)
        if user:
            members_names.append(user['username'])
    
    await message.answer(
        f"✅ Команда \"{team['name']}\" успешно создана!\n\n"
        f"Участники:\n" + "\n".join(f"👤 {name}" for name in members_names)
    )
    
    # Возвращаемся в меню управления командами
    keyboard = get_team_management_keyboard()
    await message.answer(
        "🏆 Управление командами\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )
    await state.finish()

async def show_teams_for_points(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        teams = await db.get_all_teams()
        if not teams:
            await callback_query.answer("Нет доступных команд!", show_alert=True)
            return

        keyboard = get_teams_points_keyboard(teams)
        await callback_query.message.edit_text(
            "📊 Управление баллами команд\n\n"
            "Выберите команду для начисления/снятия баллов:",
            reply_markup=keyboard
        )
        await TeamManagement.managing_points.set()  # Устанавливаем состояние
        await callback_query.answer()
    except Exception as e:
        print(f"Error in show_teams_for_points: {e}")
        await callback_query.answer("Произошла ошибка", show_alert=True)

async def show_team_points_actions(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        team_id = callback_query.data.replace("manage_team_points_", "")
        team = await db.get_team(team_id)
        
        if not team:
            await callback_query.answer("Команда не найдена!", show_alert=True)
            return
        
        await state.update_data(team_id=team_id)
        
        text = f"⭐️ Управление баллами команды \"{team['name']}\"\n"
        text += f"Текущий счет: {team['points']} баллов\n\n"
        text += "Введите количество баллов:\n"
        text += "• Положительное число для начисления (например: 5)\n"
        text += "• Отрицательное число для снятия (например: -3)"
        
        await callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("◀️ Назад", callback_data="back_to_teams_list")
            )
        )
        await TeamManagement.entering_points.set()
        await callback_query.answer()
    except Exception as e:
        print(f"Error in show_team_points_actions: {e}")
        await callback_query.answer("Произошла ошибка", show_alert=True)

async def handle_points_action(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        if callback_query.data.startswith("custom_points_"):
            team_id = callback_query.data.split('_')[2]
            await state.update_data(team_id=team_id)
            await callback_query.message.edit_text(
                "Введите количество баллов (положительное число для начисления, отрицательное для снятия):"
            )
            await TeamManagement.entering_points.set()
        else:
            action, team_id, points = callback_query.data.split('_')
            points = int(points)
            if action == "remove":
                points = -points
            
            await state.update_data(
                points_to_add=points,
                team_id=team_id
            )
            
            await callback_query.message.edit_text(
                f"Укажите причину {'начисления' if points > 0 else 'снятия'} {abs(points)} баллов:"
            )
            await TeamManagement.entering_reason.set()
        await callback_query.answer()
    except Exception as e:
        print(f"Error in handle_points_action: {e}")
        await callback_query.answer("Произошла ошибка", show_alert=True)

async def process_custom_points(message: types.Message, state: FSMContext):
    try:
        points = int(message.text)
        data = await state.get_data()
        team_id = data['team_id']
        team = await db.get_team(team_id)
        
        if not team:
            await message.answer("Команда не найдена!")
            await state.finish()
            return
        
        await state.update_data(points_to_add=points)
        await message.answer(
            f"Укажите причину {'начисления' if points > 0 else 'снятия'} {abs(points)} баллов:"
        )
        await TeamManagement.entering_reason.set()
    except ValueError:
        await message.answer(
            "Пожалуйста, введите целое число.\n"
            "• Положительное для начисления (например: 5)\n"
            "• Отрицательное для снятия (например: -3)"
        )
    except Exception as e:
        print(f"Error in process_custom_points: {e}")
        await message.answer("Произошла ошибка. Попробуйте еще раз.")

async def process_points_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    points = data['points_to_add']
    team_id = data['team_id']
    
    # Обновляем баллы команды
    team = await db.add_team_points(
        team_id=team_id,
        points=points,
        reason=message.text,
        admin_id=message.from_user.id
    )
    
    if team:
        await message.answer(
            f"✅ Баллы {'начислены' if points > 0 else 'сняты'}!\n\n"
            f"Команда: {team['name']}\n"
            f"{'Начислено' if points > 0 else 'Снято'}: {abs(points)} баллов\n"
            f"Причина: {message.text}\n"
            f"Текущий счет: {team['points']} баллов"
        )
    
    # Возвращаемся к списку команд
    teams = await db.get_all_teams()
    keyboard = get_teams_points_keyboard(teams)
    await message.answer(
        "📊 Управление баллами команд\n\n"
        "Выберите команду для начисления/снятия баллов:",
        reply_markup=keyboard
    )
    await state.finish()

async def show_points_history(callback_query: types.CallbackQuery):
    teams = await db.get_all_teams()
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for team in teams:
        keyboard.add(InlineKeyboardButton(
            f"📊 {team['name']} ({team['points']} баллов)", 
            callback_data=f"show_team_history_{team['id']}"
        ))
    
    keyboard.add(
        InlineKeyboardButton("📥 Выгрузить полную историю", callback_data="download_history"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_team_management")
    )
    
    await callback_query.message.edit_text(
        "📋 История начислений\n\n"
        "Выберите команду для просмотра последних операций:",
        reply_markup=keyboard
    )

async def show_team_history(callback_query: types.CallbackQuery):
    try:
        team_id = callback_query.data.replace("show_team_history_", "")
        team = await db.get_team(team_id)
        if not team:
            await callback_query.answer("Команда не найдена!", show_alert=True)
            return
            
        history = await db.get_team_points_history(team_id)
        
        text = f"📊 История команды \"{team['name']}\"\n"
        text += f"{'─' * 30}\n\n"
        text += f"💰 Текущий баланс: {team['points']} баллов\n\n"
        
        if not history:
            text += "📋 Операций пока нет"
        else:
            text += "📋 Последние операции:\n\n"
            # Берем последние 5 операций
            for entry in reversed(history[-5:]):
                sign = "+" if entry["points"] > 0 else ""
                text += f"{'💚' if entry['points'] > 0 else '❤️'} {sign}{entry['points']} баллов\n"
                text += f"└ Причина: {entry['reason']}\n"
                text += f"└ 🕒 {datetime.fromisoformat(entry['timestamp']).strftime('%d.%m.%Y %H:%M')}\n\n"
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("◀️ Назад к списку команд", callback_data="points_history"),
            InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_team_management")
        )
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        print(f"Error in show_team_history: {e}")
        await callback_query.answer("Произошла ошибка при загрузке истории", show_alert=True)

async def download_points_history(callback_query: types.CallbackQuery):
    teams = await db.get_all_teams()
    if not teams:
        await callback_query.answer("Нет данных для выгрузки!", show_alert=True)
        return

    # Создаем данные для Excel
    data = []
    for team in teams:
        history = await db.get_team_points_history(team['id'])
        for record in history:
            admin = await db.get_user(record['admin_id'])
            admin_name = admin['username'] if admin else "Неизвестный"
            data.append({
                'Команда': team['name'],
                'Баллы': record['points'],
                'Причина': record['reason'],
                'Администратор': admin_name,
                'Дата': datetime.fromisoformat(record['timestamp']).strftime("%d.%m.%Y %H:%M")
            })
    
    if not data:
        await callback_query.answer("Нет данных для выгрузки!", show_alert=True)
        return
    
    # Создаем DataFrame и сохраняем в Excel
    df = pd.DataFrame(data)
    
    # Создаем буфер для файла
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='История баллов')
    
    excel_buffer.seek(0)
    
    # Формируем имя файла с текущей датой
    current_date = datetime.now().strftime("%Y%m%d")
    filename = f"points_history_{current_date}.xlsx"
    
    # Отправляем файл
    await callback_query.message.answer_document(
        document=("points_history.xlsx", excel_buffer),
        caption="📊 История начисления баллов"
    )
    await callback_query.answer()

async def show_teams_for_edit(callback_query: types.CallbackQuery):
    teams = await db.get_all_teams()
    if not teams:
        await callback_query.answer("Нет доступных команд!", show_alert=True)
        return

    keyboard = get_teams_edit_keyboard(teams)
    await callback_query.message.edit_text(
        "✏️ Редактирование команд\n\n"
        "Выберите команду для редактирования:",
        reply_markup=keyboard
    )
    await TeamEditing.selecting_team.set()
    await callback_query.answer()

async def edit_team(callback_query: types.CallbackQuery, state: FSMContext):
    if callback_query.data == "back_to_teams_list":
        teams = await db.get_all_teams()
        keyboard = get_teams_edit_keyboard(teams)
        await callback_query.message.edit_text(
            "✏️ Редактирование команд\n\n"
            "Выберите команду для редактирования:",
            reply_markup=keyboard
        )
        return

    team_id = callback_query.data.replace("edit_team_", "")
    team = await db.get_team(team_id)
    
    if not team:
        await callback_query.answer("Команда не найдена!", show_alert=True)
        return
    
    await state.update_data(current_team_id=team_id)
    
    members = []
    for member_id in team['members']:
        user = await db.get_user(int(member_id))
        if user:
            members.append(user)
    
    text = f"✏️ Редактирование команды \"{team['name']}\"\n\n"
    text += "• Нажмите на участника, чтобы удалить его\n"
    text += "• Используйте кнопки внизу для других действий"
    
    keyboard = get_team_edit_keyboard(team, members)
    await callback_query.message.edit_text(text, reply_markup=keyboard)

async def remove_team_member(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        # Формат: remove_member_{team_id}_{user_id}
        parts = callback_query.data.split('_')
        if len(parts) == 4:  # Проверяем, что у нас правильное количество частей
            team_id = parts[2]
            user_id = int(parts[3])
            
            print(f"Removing user {user_id} from team {team_id}")
            
            # Удаляем участника
            await db.remove_team_member(team_id, user_id)
            
            # Получаем обновленную информацию о команде
            team = await db.get_team(team_id)
            if not team:
                await callback_query.answer("Команда не найдена!", show_alert=True)
                return
            
            # Получаем обновленный список участников
            members = []
            for member_id in team['members']:
                user = await db.get_user(int(member_id))
                if user:
                    members.append(user)
            
            # Обновляем отображение команды
            text = f"✏️ Редактирование команды \"{team['name']}\"\n\n"
            text += "• Нажмите на участника, чтобы удалить его\n"
            text += "• Используйте кнопки внизу для других действий"
            
            keyboard = get_team_edit_keyboard(team, members)
            await callback_query.message.edit_text(text, reply_markup=keyboard)
            await callback_query.answer("Участник удален из команды")
        else:
            await callback_query.answer("Ошибка формата данных", show_alert=True)
    except Exception as e:
        print(f"Error in remove_team_member: {e}")
        await callback_query.answer("Произошла ошибка при удалении участника", show_alert=True)

async def delete_team(callback_query: types.CallbackQuery):
    team_id = callback_query.data.replace("delete_team_", "")
    await db.delete_team(team_id)
    
    # Возвращаемся к списку команд
    teams = await db.get_all_teams()
    keyboard = get_teams_edit_keyboard(teams)
    await callback_query.message.edit_text(
        "✏️ Редактирование команд\n\n"
        "Выберите команду для редактирования:",
        reply_markup=keyboard
    )
    await callback_query.answer("Команда удалена")

async def start_add_member(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        team_id = callback_query.data.replace("add_member_", "")
        team = await db.get_team(team_id)
        
        if not team:
            await callback_query.answer("Команда не найдена!", show_alert=True)
            return
        
        # Получаем список доступных пользователей
        all_users = await db.get_all_users()
        team_members = set(int(m) for m in team['members'])
        available_users = [u for u in all_users if u['telegram_id'] not in team_members]
        
        if not available_users:
            await callback_query.answer("Нет доступных участников для добавления!", show_alert=True)
            return
        
        await state.update_data(current_team_id=team_id)
        keyboard = get_members_selection_keyboard(available_users)
        
        await callback_query.message.edit_text(
            f"Выберите участника для добавления в команду \"{team['name']}\":",
            reply_markup=keyboard
        )
        await TeamEditing.adding_member.set()
    except Exception as e:
        print(f"Error in start_add_member: {e}")
        await callback_query.answer("Произошла ошибка", show_alert=True)

async def add_team_member(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        member_id = int(callback_query.data.replace("select_member_", ""))
        data = await state.get_data()
        team_id = data.get('current_team_id')
        
        if not team_id:
            await callback_query.answer("Ошибка: не найден ID команды", show_alert=True)
            return
        
        # Добавляем участника
        await db.add_team_member(team_id, member_id)
        
        # Получаем обновленную информацию
        team = await db.get_team(team_id)
        members = []
        for member_id in team['members']:
            user = await db.get_user(int(member_id))
            if user:
                members.append(user)
        
        # Обновляем отображение команды
        text = f"✏️ Редактирование команды \"{team['name']}\"\n\n"
        text += "• Нажмите на участника, чтобы удалить его\n"
        text += "• Используйте кнопки внизу для других действий"
        
        keyboard = get_team_edit_keyboard(team, members)
        await callback_query.message.edit_text(text, reply_markup=keyboard)
        await callback_query.answer("Участник добавлен в команду")
        await state.finish()
    except Exception as e:
        print(f"Error in add_team_member: {e}")
        await callback_query.answer("Произошла ошибка при добавлении участника", show_alert=True)

async def show_rating(callback_query: types.CallbackQuery):
    teams = await db.get_all_teams()
    if not teams:
        await callback_query.answer("Нет доступных команд!", show_alert=True)
        return
    
    # Сортируем команды по баллам
    teams_sorted = sorted(teams, key=lambda x: x['points'], reverse=True)
    
    text = "🏆 РЕЙТИНГ КОМАНД\n\n"
    
    for i, team in enumerate(teams_sorted, 1):
        # Добавляем эмодзи для топ-3
        prefix = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{prefix} {team['name']}\n"
        text += f"└ {team['points']} баллов\n"
        # Получаем участников команды
        members = []
        for member_id in team['members']:
            user = await db.get_user(int(member_id))
            if user:
                members.append(user['username'])
        text += f"👥 Участники: {', '.join(members)}\n\n"
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📢 Опубликовать рейтинг", callback_data="publish_rating"),
        InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
    )
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()

async def publish_rating(callback_query: types.CallbackQuery):
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
    
    await callback_query.bot.send_message(config.GROUP_CHAT_ID, text)
    await callback_query.answer("Рейтинг опубликован в общем чате!")

async def show_members_statistics(callback_query: types.CallbackQuery):
    try:
        users = await db.get_all_users()
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        for user in users:
            # Добавляем callback_data с правильным форматом
            keyboard.add(InlineKeyboardButton(
                f"{'👑' if user['is_admin'] else '👤'} {user['username']}", 
                callback_data=f"user_stats_{user['telegram_id']}"
            ))
        
        keyboard.add(
            InlineKeyboardButton("📊 Опубликовать рейтинг посещений", callback_data="publish_attendance_rating"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_admin")
        )
        
        await callback_query.message.edit_text(
            "📈 СТАТИСТИКА УЧАСТНИКОВ\n"
            f"{'─' * 30}\n\n"
            "👑 - администратор\n"
            "👤 - участник\n\n"
            "Выберите пользователя для просмотра статистики:",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"Error in show_members_statistics: {e}")
        await callback_query.answer("Произошла ошибка при загрузке списка", show_alert=True)

async def show_user_stats(callback_query: types.CallbackQuery):
    try:
        user_id = int(callback_query.data.replace("user_stats_", ""))
        user = await db.get_user(user_id)
        
        # Получаем статистику из базы
        stats = await db.get_user_attendance_stats(user_id)
        
        text = (
            f"👤 Статистика посещений: {user['username']}\n"
            f"{'─' * 30}\n\n"
            f"📅 Всего отметок: {stats['total_marked']}\n\n"
            f"✅ Присутствовал: {stats['present']} ({(stats['present']/stats['total_marked']*100):.1f}% если был)\n"
            f"❌ Отсутствовал: {stats['absent']} ({(stats['absent']/stats['total_marked']*100):.1f}% если был)"
        )
        
        # Добавляем информацию о пропусках подряд
        if stats['consecutive_absences'] > 1:
            text += f" ⚠️ {stats['consecutive_absences']} раз подряд"
        
        text += (
            f"\n⚠️ По ув. причине: {stats['excused']} ({(stats['excused']/stats['total_marked']*100):.1f}% если был)\n\n"
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
        
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("◀️ Назад к списку", callback_data="show_members_statistics"),
            InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_admin")
        )
        
        await callback_query.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        print(f"Error in show_user_stats: {e}")
        await callback_query.answer("Произошла ошибка при загрузке статистики", show_alert=True)

async def publish_attendance_rating(callback_query: types.CallbackQuery):
    users = await db.get_all_users()
    attendance = await db.get_attendance()
    
    stats = []
    for user in users:
        total_marked = 0
        present = 0
        
        for date in attendance:
            if str(user['telegram_id']) in attendance[date]:
                total_marked += 1
                if attendance[date][str(user['telegram_id'])]["status"] == "present":
                    present += 1
        
        if total_marked > 0:
            attendance_rate = (present / total_marked * 100)
            stats.append((user['username'], attendance_rate, present, total_marked))
    
    # Сортируем по проценту посещений
    stats.sort(key=lambda x: x[1], reverse=True)
    
    text = "📊 РЕЙТИНГ ПОСЕЩАЕМОСТИ\n"
    text += f"{'─' * 30}\n\n"
    
    for i, (username, rate, present, total) in enumerate(stats, 1):
        prefix = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        stars = "⭐️" * (5 if rate >= 90 else 4 if rate >= 75 else 3 if rate >= 60 else 2 if rate >= 40 else 1)
        text += f"{prefix} {username}\n"
        text += f"└ {rate:.1f}% ({present}/{total}) {stars}\n\n"
    
    await callback_query.bot.send_message(config.GROUP_CHAT_ID, text)
    await callback_query.answer("Рейтинг посещений опубликован!")

def register_handlers(dp: Dispatcher):
    dp.register_message_handler(admin_panel, commands=["admin"], state="*")
    dp.register_callback_query_handler(manage_admins, text="manage_admins")
    dp.register_callback_query_handler(manage_admins, text="back_to_admin", state=AdminManagement.managing)
    dp.register_callback_query_handler(
        toggle_admin_rights,
        lambda c: c.data.startswith("toggle_admin_"),
        state=AdminManagement.managing
    )
    dp.register_callback_query_handler(start_attendance_marking, text="mark_attendance")
    dp.register_callback_query_handler(
        handle_attendance_mark,
        lambda c: c.data.startswith(("mark_", "finish_", "back_")),
        state=AttendanceMarking.marking
    )
    dp.register_message_handler(cmd_create_team, commands=["create_team"])
    dp.register_message_handler(cmd_add_member, commands=["add_member"])
    dp.register_callback_query_handler(process_team_selection, 
                                     lambda c: c.data.startswith("select_team_"),
                                     state=TeamMemberAdd.waiting_for_team)
    dp.register_message_handler(process_member_username, 
                              state=TeamMemberAdd.waiting_for_username)
    dp.register_callback_query_handler(team_management, text="manage_teams")
    dp.register_callback_query_handler(start_team_creation, text="create_team")
    dp.register_callback_query_handler(
        toggle_member_selection,
        lambda c: c.data.startswith("select_member_"),
        state=TeamManagement.selecting_members
    )
    dp.register_callback_query_handler(
        confirm_member_selection,
        text="confirm_members",
        state=TeamManagement.selecting_members
    )
    dp.register_message_handler(
        process_team_name,
        state=TeamManagement.entering_name
    )
    dp.register_callback_query_handler(show_teams_for_points, text="manage_points")
    dp.register_callback_query_handler(
        show_team_points_actions,
        lambda c: c.data.startswith("manage_team_points_")
    )
    dp.register_callback_query_handler(
        handle_points_action,
        lambda c: c.data.startswith(("add_points_", "remove_points_", "custom_points_")),
        state=TeamManagement.managing_points
    )
    dp.register_message_handler(
        process_custom_points,
        state=TeamManagement.entering_points
    )
    dp.register_message_handler(
        process_points_reason,
        state=TeamManagement.entering_reason
    )
    dp.register_callback_query_handler(show_points_history, text="points_history")
    dp.register_callback_query_handler(
        download_points_history,
        text="download_history",
        state="*"
    )
    dp.register_callback_query_handler(
        team_management,
        lambda c: c.data in ["back_to_admin", "back_to_team_management", "back_to_teams_list"],
        state="*"
    )
    dp.register_callback_query_handler(show_teams_for_edit, text="edit_teams")
    dp.register_callback_query_handler(
        edit_team,
        lambda c: c.data.startswith("edit_team_"),
        state=TeamEditing.selecting_team
    )
    dp.register_callback_query_handler(
        remove_team_member,
        lambda c: c.data.startswith("remove_member_"),
        state="*"
    )
    dp.register_callback_query_handler(
        delete_team,
        lambda c: c.data.startswith("delete_team_"),
        state="*"
    )
    dp.register_callback_query_handler(
        start_add_member,
        lambda c: c.data.startswith("add_member_"),
        state="*"
    )
    dp.register_callback_query_handler(
        add_team_member,
        lambda c: c.data.startswith("select_member_"),
        state=TeamEditing.adding_member
    )
    dp.register_callback_query_handler(show_rating, text="show_rating")
    dp.register_callback_query_handler(publish_rating, text="publish_rating")
    dp.register_callback_query_handler(
        show_members_statistics, 
        text="show_members_statistics",
        state="*"
    )
    dp.register_callback_query_handler(
        show_user_stats, 
        lambda c: c.data.startswith("user_stats_"),
        state="*"
    )
    dp.register_callback_query_handler(publish_attendance_rating, text="publish_attendance_rating") 