import functools
from typing import Callable
from utils.logger import logger

def log_errors(func: Callable) -> Callable:
    """Декоратор для логирования ошибок"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Ошибка в {func.__name__}: {str(e)}", 
                exc_info=True,
                extra={
                    'args': args,
                    'kwargs': kwargs
                }
            )
            raise
    return wrapper 