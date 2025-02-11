import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import config
from handlers import admin, common, rating, user
from database import init_db
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Регистрация хендлеров
user.register_handlers(dp)
admin.register_handlers(dp)
rating.register_handlers(dp)
common.register_handlers(dp)

async def main():
    # Инициализация базы данных
    await init_db()
    
    # Запуск бота
    try:
        await dp.start_polling()
    finally:
        await bot.session.close()

async def mark_attendance(self, user_id: int, status: str, marked_by: int):
    attendance = self._load_json(self.attendance_file)
    current_date = datetime.now().date().isoformat()
    
    if current_date not in attendance:
        attendance[current_date] = {}
    
    # Получаем все даты и сортируем их от новых к старым
    dates = sorted(attendance.keys(), reverse=True)
    consecutive_absences = 0
    
    print(f"Marking attendance for user {user_id} with status {status}")
    
    if status == "absent":
        # Проверяем предыдущие даты
        for prev_date in dates:
            if prev_date == current_date:  # Пропускаем текущую дату
                continue
                
            if str(user_id) in attendance[prev_date]:
                prev_status = attendance[prev_date][str(user_id)]["status"]
                prev_consecutive = attendance[prev_date][str(user_id)].get("consecutive_absences", 0)
                
                print(f"Previous date: {prev_date}, status: {prev_status}, consecutive: {prev_consecutive}")
                
                if prev_status == "absent":
                    # Если предыдущая отметка тоже пропуск, берем её значение и добавляем 1
                    consecutive_absences = prev_consecutive + 1
                    print(f"Found previous absent, increasing to: {consecutive_absences}")
                else:
                    # Если предыдущая отметка не пропуск, это первый пропуск
                    consecutive_absences = 1
                    print(f"Previous was not absent, setting to: {consecutive_absences}")
                break
            else:
                # Если нет предыдущей отметки, это первый пропуск
                consecutive_absences = 1
                print(f"No previous record, setting to: {consecutive_absences}")
                break
        
        # Если не нашли предыдущих отметок, это первый пропуск
        if consecutive_absences == 0:
            consecutive_absences = 1
            print(f"No previous dates, setting to: {consecutive_absences}")
    
    print(f"Final consecutive absences: {consecutive_absences}")
    
    attendance[current_date][str(user_id)] = {
        "status": status,
        "marked_by": marked_by,
        "timestamp": datetime.now().isoformat(),
        "consecutive_absences": consecutive_absences
    }
    
    self._save_json(attendance, self.attendance_file)

if __name__ == '__main__':
    asyncio.run(main()) 