from aiogram import Dispatcher, types
from database.json_storage import db
from config import config

async def cmd_start(message: types.Message):
    # Проверяем, существует ли пользователь
    user = await db.get_user(message.from_user.id)
    
    if not user:
        # Создаем нового пользователя
        await db.create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            is_admin=message.from_user.id == config.ADMIN_ID
        )
        await message.answer("Добро пожаловать! Вы успешно зарегистрированы в системе.")
    else:
        await message.answer("С возвращением!")

def register_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=["start"]) 