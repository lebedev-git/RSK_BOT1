from typing import Optional, Any, Dict
from utils.logger import logger

class BotError(Exception):
    """Базовый класс для ошибок бота"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        logger.error(f"{message} | Детали: {details}")
        super().__init__(self.message)

class DatabaseError(BotError):
    """Ошибки при работе с базой данных"""
    pass

class UserError(BotError):
    """Ошибки, связанные с пользователями"""
    pass

class TeamError(BotError):
    """Ошибки, связанные с командами"""
    pass 