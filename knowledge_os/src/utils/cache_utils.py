"""
Модуль для безопасного кэширования данных
"""

import inspect
import time
from functools import wraps
from typing import Any, Dict, Optional


class CacheManager:
    """Менеджер кэша для безопасного хранения данных (🚀 STATELESS VERSION)"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._instance._cache_data = {}
            cls._instance._cache_timestamps = {}
        return cls._instance

    def __init__(self):
        # Инициализация уже проведена в __new__ для синглтона
        pass

    def get(self, key: str, max_age: float = 30.0) -> Optional[Any]:
        """
        Получить данные из кэша

        Args:
            key: Ключ кэша
            max_age: Максимальный возраст данных в секундах

        Returns:
            Данные из кэша или None если данные устарели или отсутствуют
        """
        if key not in self._cache_data:
            return None

        timestamp = self._cache_timestamps.get(key, 0)
        if time.time() - timestamp > max_age:
            # Удаляем устаревшие данные
            self.delete(key)
            return None

        return self._cache_data[key]

    def set(self, key: str, value: Any) -> None:
        """
        Сохранить данные в кэш

        Args:
            key: Ключ кэша
            value: Значение для сохранения
        """
        self._cache_data[key] = value
        self._cache_timestamps[key] = time.time()

    def delete(self, key: str) -> None:
        """
        Удалить данные из кэша

        Args:
            key: Ключ кэша
        """
        if key in self._cache_data:
            del self._cache_data[key]
        if key in self._cache_timestamps:
            del self._cache_timestamps[key]

    def clear(self) -> None:
        """Очистить весь кэш"""
        self._cache_data.clear()
        self._cache_timestamps.clear()

    def exists(self, key: str) -> bool:
        """
        Проверить существование ключа в кэше

        Args:
            key: Ключ кэша

        Returns:
            True если ключ существует
        """
        return key in self._cache_data


def cache_with_ttl(ttl_seconds: float = 30.0):
    """
    Декоратор для кэширования функций с TTL (🚀 STATELESS VERSION)
    """

    def decorator(func):
        # Получаем синглтон менеджер кэша
        cache_manager = CacheManager()

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                no_cache = bool(kwargs.pop("_no_cache", False))
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
                if not no_cache:
                    cached_result = cache_manager.get(cache_key, ttl_seconds)
                    if cached_result is not None:
                        return cached_result

                result = await func(*args, **kwargs)
                if not no_cache:
                    cache_manager.set(cache_key, result)
                return result

            return async_wrapper

        # Синхронная функция
        @wraps(func)
        def wrapper(*args, **kwargs):
            no_cache = bool(kwargs.pop("_no_cache", False))
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            if not no_cache:
                cached_result = cache_manager.get(cache_key, ttl_seconds)
                if cached_result is not None:
                    return cached_result

            result = func(*args, **kwargs)
            if not no_cache:
                cache_manager.set(cache_key, result)
            return result

        return wrapper

    return decorator
