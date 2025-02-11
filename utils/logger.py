import logging
import os
from datetime import datetime

# Настраиваем логирование
def setup_logger():
    # Создаем директорию для логов если её нет
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Создаем форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Создаем файловый обработчик
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f'bot_{datetime.now().strftime("%Y%m%d")}.log'),
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Создаем консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Настраиваем корневой логгер
    logger = logging.getLogger('bot')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Создаем логгер
logger = setup_logger() 