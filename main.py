import asyncio
import logging
from typing import Optional, NoReturn
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import config
from handlers import admin, common, rating, user
from database import init_db
from utils.logger import logger

async def main() -> NoReturn:
    """Основная функция запуска бота"""
    try:
        # Инициализация бота и диспетчера
        bot = Bot(token=config.BOT_TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(bot, storage=storage)
        
        # Регистрация хендлеров
        logger.info("Регистрация хендлеров...")
        user.register_handlers(dp)
        admin.register_handlers(dp)
        rating.register_handlers(dp)
        common.register_handlers(dp)
        
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        await init_db()
        
        # Запуск бота
        logger.info("Бот запущен")
        await dp.start_polling()
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise
    finally:
        if bot:
            await bot.session.close()
            logger.info("Сессия бота закрыта")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен") 