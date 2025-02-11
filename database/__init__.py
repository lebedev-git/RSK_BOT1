from .json_storage import db

async def init_db():
    """
    Функция инициализации базы данных.
    В случае с JSON просто убеждаемся, что все файлы созданы
    """
    # JsonStorage создаст все необходимые файлы при инициализации
    pass 