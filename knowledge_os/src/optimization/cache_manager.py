"""
Менеджер кэширования для оптимизации производительности
"""

import time
import hashlib
import pickle
import logging
from typing import Any, Optional, Dict, Callable, Union
from functools import wraps
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class CacheManager:
    """Менеджер кэширования"""
    
    def __init__(self, cache_dir: str = "cache", max_size: int = 1000, ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.max_size = max_size
        self.ttl = ttl  # Time to live in seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, float] = {}
        
    def _generate_key(self, func_name: str, args: tuple, kwargs: dict) -> str:
        """Генерация ключа кэша"""
        try:
            # Создание хэша из аргументов
            args_str = str(args) + str(sorted(kwargs.items()))
            key_hash = hashlib.md5(args_str.encode()).hexdigest()
            return f"{func_name}_{key_hash}"
        except Exception as e:
            logger.error(f"Ошибка генерации ключа кэша: {e}")
            return f"{func_name}_{int(time.time())}"
    
    def _is_expired(self, timestamp: float) -> bool:
        """Проверка истечения срока действия кэша"""
        return time.time() - timestamp > self.ttl
    
    def _cleanup_expired(self):
        """Очистка истекших записей"""
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, data in self.cache.items():
                if self._is_expired(data['timestamp']):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
            
            if expired_keys:
                logger.debug(f"Очищено {len(expired_keys)} истекших записей кэша")
                
        except Exception as e:
            logger.error(f"Ошибка очистки истекших записей: {e}")
    
    def _cleanup_lru(self):
        """Очистка по принципу LRU"""
        try:
            if len(self.cache) <= self.max_size:
                return
            
            # Сортировка по времени доступа
            sorted_keys = sorted(self.access_times.items(), key=lambda x: x[1])
            
            # Удаление старых записей
            keys_to_remove = len(self.cache) - self.max_size + 100  # Удаляем с запасом
            
            for key, _ in sorted_keys[:keys_to_remove]:
                if key in self.cache:
                    del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
            
            logger.debug(f"Очищено {keys_to_remove} записей по LRU")
            
        except Exception as e:
            logger.error(f"Ошибка очистки LRU: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        try:
            if key not in self.cache:
                return None
            
            data = self.cache[key]
            
            # Проверка истечения срока
            if self._is_expired(data['timestamp']):
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
                return None
            
            # Обновление времени доступа
            self.access_times[key] = time.time()
            
            logger.debug(f"Значение получено из кэша: {key}")
            return data['value']
            
        except Exception as e:
            logger.error(f"Ошибка получения из кэша: {e}")
            return None
    
    def set(self, key: str, value: Any) -> bool:
        """Сохранение значения в кэш"""
        try:
            # Очистка истекших записей
            self._cleanup_expired()
            
            # Очистка по LRU если нужно
            if len(self.cache) >= self.max_size:
                self._cleanup_lru()
            
            # Сохранение значения
            self.cache[key] = {
                'value': value,
                'timestamp': time.time()
            }
            self.access_times[key] = time.time()
            
            logger.debug(f"Значение сохранено в кэш: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в кэш: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Удаление значения из кэша"""
        try:
            if key in self.cache:
                del self.cache[key]
            if key in self.access_times:
                del self.access_times[key]
            
            logger.debug(f"Значение удалено из кэша: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления из кэша: {e}")
            return False
    
    def clear(self):
        """Очистка всего кэша"""
        try:
            self.cache.clear()
            self.access_times.clear()
            logger.info("Кэш полностью очищен")
            
        except Exception as e:
            logger.error(f"Ошибка очистки кэша: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        try:
            current_time = time.time()
            expired_count = 0
            
            for data in self.cache.values():
                if self._is_expired(data['timestamp']):
                    expired_count += 1
            
            return {
                'total_entries': len(self.cache),
                'expired_entries': expired_count,
                'max_size': self.max_size,
                'ttl': self.ttl,
                'hit_rate': getattr(self, '_hit_count', 0) / max(getattr(self, '_access_count', 1), 1)
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики кэша: {e}")
            return {}
    
    def save_to_disk(self, filename: str = "cache.pkl"):
        """Сохранение кэша на диск"""
        try:
            cache_file = self.cache_dir / filename
            
            # Подготовка данных для сохранения
            cache_data = {
                'cache': self.cache,
                'access_times': self.access_times,
                'timestamp': time.time()
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            logger.info(f"Кэш сохранен на диск: {cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения кэша на диск: {e}")
            return False
    
    def load_from_disk(self, filename: str = "cache.pkl"):
        """Загрузка кэша с диска"""
        try:
            cache_file = self.cache_dir / filename
            
            if not cache_file.exists():
                logger.warning(f"Файл кэша не найден: {cache_file}")
                return False
            
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)
            
            # Проверка возраста кэша
            if time.time() - cache_data['timestamp'] > self.ttl:
                logger.warning("Кэш на диске устарел")
                return False
            
            self.cache = cache_data['cache']
            self.access_times = cache_data['access_times']
            
            logger.info(f"Кэш загружен с диска: {cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка загрузки кэша с диска: {e}")
            return False


class FunctionCache:
    """Кэширование результатов функций"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self._hit_count = 0
        self._access_count = 0
    
    def cached(self, ttl: Optional[int] = None):
        """
        Декоратор для кэширования результатов функции
        
        Args:
            ttl: Время жизни кэша в секундах
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    # Генерация ключа кэша
                    key = self.cache_manager._generate_key(func.__name__, args, kwargs)
                    
                    # Попытка получения из кэша
                    cached_result = self.cache_manager.get(key)
                    if cached_result is not None:
                        self._hit_count += 1
                        logger.debug(f"Результат получен из кэша для {func.__name__}")
                        return cached_result
                    
                    # Выполнение функции
                    result = func(*args, **kwargs)
                    
                    # Сохранение в кэш
                    self.cache_manager.set(key, result)
                    
                    self._access_count += 1
                    logger.debug(f"Результат сохранен в кэш для {func.__name__}")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Ошибка кэширования функции {func.__name__}: {e}")
                    return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def get_hit_rate(self) -> float:
        """Получение коэффициента попаданий в кэш"""
        return self._hit_count / max(self._access_count, 1)


class DataCache:
    """Кэширование данных"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
    
    def cache_dataframe(self, key: str, df, ttl: int = 3600):
        """Кэширование DataFrame"""
        try:
            # Сериализация DataFrame
            df_bytes = df.to_pickle()
            
            # Сохранение в кэш
            cache_key = f"df_{key}"
            self.cache_manager.set(cache_key, df_bytes)
            
            logger.debug(f"DataFrame закэширован: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка кэширования DataFrame: {e}")
            return False
    
    def get_cached_dataframe(self, key: str):
        """Получение DataFrame из кэша"""
        try:
            cache_key = f"df_{key}"
            df_bytes = self.cache_manager.get(cache_key)
            
            if df_bytes is None:
                return None
            
            # Десериализация DataFrame
            df = pd.read_pickle(df_bytes)
            
            logger.debug(f"DataFrame получен из кэша: {key}")
            return df
            
        except Exception as e:
            logger.error(f"Ошибка получения DataFrame из кэша: {e}")
            return None
    
    def cache_json(self, key: str, data: dict, ttl: int = 3600):
        """Кэширование JSON данных"""
        try:
            cache_key = f"json_{key}"
            self.cache_manager.set(cache_key, data)
            
            logger.debug(f"JSON данные закэшированы: {key}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка кэширования JSON: {e}")
            return False
    
    def get_cached_json(self, key: str):
        """Получение JSON данных из кэша"""
        try:
            cache_key = f"json_{key}"
            data = self.cache_manager.get(cache_key)
            
            if data is None:
                return None
            
            logger.debug(f"JSON данные получены из кэша: {key}")
            return data
            
        except Exception as e:
            logger.error(f"Ошибка получения JSON из кэша: {e}")
            return None


# Глобальные экземпляры
cache_manager = CacheManager()
function_cache = FunctionCache(cache_manager)
data_cache = DataCache(cache_manager)


def cached_function(ttl: Optional[int] = None):
    """Удобная функция для кэширования функций"""
    return function_cache.cached(ttl)


def cache_dataframe(key: str, df, ttl: int = 3600):
    """Удобная функция для кэширования DataFrame"""
    return data_cache.cache_dataframe(key, df, ttl)


def get_cached_dataframe(key: str):
    """Удобная функция для получения DataFrame из кэша"""
    return data_cache.get_cached_dataframe(key)


def cache_json(key: str, data: dict, ttl: int = 3600):
    """Удобная функция для кэширования JSON"""
    return data_cache.cache_json(key, data, ttl)


def get_cached_json(key: str):
    """Удобная функция для получения JSON из кэша"""
    return data_cache.get_cached_json(key)
