import asyncio
import logging
from typing import Optional, NoReturn
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import config
from handlers import admin, common, rating, user
from database import init_db
from utils.logger import logger
import sys
import signal
from utils.process_guard import SingleInstance

async def on_shutdown(dp: Dispatcher):
    """Действия при завершении работы"""
    try:
        logger.info("Завершение работы бота...")
        await dp.storage.close()
        await dp.storage.wait_closed()
        session = await dp.bot.get_session()
        if session:
            await session.close()
        # Сбрасываем webhook для избежания конфликтов при следующем запуске
        await dp.bot.delete_webhook()
        logger.info("Бот успешно остановлен")
    except Exception as e:
        logger.error(f"Ошибка при остановке бота: {e}")

async def main() -> NoReturn:
    """Основная функция запуска бота"""
    # Создаем объекты бота и диспетчера
    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
    
    try:
        # Сбрасываем webhook перед запуском polling
        await bot.delete_webhook()
        
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
        await dp.start_polling(reset_webhook=True)
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise
    finally:
        await on_shutdown(dp)

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info("Получен сигнал завершения, закрываем бота...")
    sys.exit(0)

if __name__ == '__main__':
    try:
        # Проверяем, не запущен ли уже бот
        instance = SingleInstance()
        
        # Регистрируем обработчик сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Запускаем бота
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        sys.exit(1) 