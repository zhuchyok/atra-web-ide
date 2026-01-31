"""
Модуль работы с базой данных.

Содержит:
- db: Основной класс работы с БД
- connection_pool: Пул соединений
- initialization: Инициализация БД
"""

__all__ = [
    'Database',
    'get_db_pool',
    'get_connection',
    'init_database',
]

# Импорты для обратной совместимости
try:
    from src.database.connection_pool import get_db_pool, get_connection
except ImportError:
    # Fallback если connection_pool недоступен
    def get_db_pool(*args, **kwargs):
        raise NotImplementedError("Connection pool отключен")
    
    def get_connection(*args, **kwargs):
        raise NotImplementedError("Connection pool отключен")

