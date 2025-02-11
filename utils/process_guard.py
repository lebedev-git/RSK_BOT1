import os
import sys
import tempfile
import psutil
from utils.logger import logger

class SingleInstance:
    def __init__(self):
        self.lockfile = os.path.join(tempfile.gettempdir(), 'RSK_BOT.lock')
        
        if os.path.exists(self.lockfile):
            try:
                with open(self.lockfile, 'r') as f:
                    pid = int(f.read().strip())
                
                # Проверяем, существует ли процесс
                if psutil.pid_exists(pid):
                    # Проверяем, является ли процесс Python-процессом
                    process = psutil.Process(pid)
                    if "python" in process.name().lower():
                        logger.error(f"Бот уже запущен (PID: {pid})")
                        logger.info("Завершаем предыдущий процесс...")
                        process.terminate()
                        process.wait()  # Ждем завершения процесса
                
                # Удаляем старый файл блокировки
                os.remove(self.lockfile)
            except (OSError, ValueError, psutil.NoSuchProcess):
                # Если процесс не существует или произошла ошибка, удаляем файл блокировки
                if os.path.exists(self.lockfile):
                    os.remove(self.lockfile)
        
        # Создаем новый файл блокировки
        with open(self.lockfile, 'w') as f:
            f.write(str(os.getpid()))
        
        logger.info(f"Создан файл блокировки (PID: {os.getpid()})")
    
    def __del__(self):
        try:
            if os.path.exists(self.lockfile):
                os.remove(self.lockfile)
                logger.info("Файл блокировки удален")
        except Exception as e:
            logger.error(f"Ошибка при удалении файла блокировки: {e}") 