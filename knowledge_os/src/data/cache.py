"""
Расширенная система кэширования данных для ATRA
"""

import time
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any, Union
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..core.config import (
    CACHE_SETTINGS,
    OHLC_CACHE_TTL,
    NEWS_CACHE_TTL,
    ANOMALY_CACHE_TTL
)

logger = logging.getLogger(__name__)


@dataclass
class CacheItem:
    """Элемент кэша с метаданными"""
    key: str
    data: Any
    timestamp: float = field(default_factory=time.time)
    ttl: int = 300  # 5 минут по умолчанию
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    size_bytes: int = 0

    def __post_init__(self):
        """Вычисление размера данных после инициализации"""
        try:
            self.size_bytes = len(json.dumps(self.data).encode('utf-8'))
        except (TypeError, ValueError):
            self.size_bytes = len(str(self.data).encode('utf-8'))

    @property
    def is_expired(self) -> bool:
        """Проверка истечения TTL"""
        return time.time() - self.timestamp > self.ttl

    @property
    def age_seconds(self) -> float:
        """Возраст элемента в секундах"""
        return time.time() - self.timestamp

    @property
    def time_to_live(self) -> float:
        """Оставшееся время жизни в секундах"""
        return max(0, self.ttl - self.age_seconds)


class DataCache(ABC):
    """Абстрактный базовый класс для кэшей данных"""

    def __init__(self, name: str, max_size: int = 1000, default_ttl: int = 300):
        self.name = name
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheItem] = {}
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def _generate_key(self, *args, **kwargs) -> str:
        """Генерация ключа кэша"""
        key_parts = [str(arg) for arg in args]
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_string = "|".join(key_parts)

        return hashlib.md5(key_string.encode('utf-8')).hexdigest()

    def _evict_oldest(self):
        """Удаление самого старого элемента"""
        if not self.cache:
            return

        oldest_key = min(self.cache.keys(),
                        key=lambda k: self.cache[k].last_access)
        del self.cache[oldest_key]
        self.evictions += 1
        logger.debug(f"Evicted from {self.name} cache: {oldest_key}")

    def _cleanup_expired(self):
        """Очистка истекших элементов"""
        expired_keys = [k for k, v in self.cache.items() if v.is_expired]
        for key in expired_keys:
            del self.cache[key]
            self.evictions += 1
        if expired_keys:
            logger.debug(f"Cleaned {len(expired_keys)} expired items from {self.name} cache")

    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """Сохранение данных в кэш"""
        try:
            if len(self.cache) >= self.max_size:
                self._evict_oldest()

            self._cleanup_expired()

            cache_item = CacheItem(
                key=key,
                data=data,
                ttl=ttl or self.default_ttl
            )

            self.cache[key] = cache_item
            logger.debug(f"Cached in {self.name}: {key} (TTL: {cache_item.ttl}s)")
            return True

        except Exception as e:
            logger.error(f"Error caching data in {self.name}: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """Получение данных из кэша"""
        try:
            if key not in self.cache:
                self.misses += 1
                return None

            cache_item = self.cache[key]

            if cache_item.is_expired:
                del self.cache[key]
                self.misses += 1
                return None

            cache_item.access_count += 1
            cache_item.last_access = time.time()
            self.hits += 1

            logger.debug(f"Cache hit in {self.name}: {key}")
            return cache_item.data

        except Exception as e:
            logger.error(f"Error retrieving from {self.name} cache: {e}")
            return None

    def delete(self, key: str) -> bool:
        """Удаление элемента из кэша"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self):
        """Очистка всего кэша"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        logger.info(f"Cleared {self.name} cache")

    def get_stats(self) -> Dict:
        """Получение статистики кэша"""
        total_size = sum(item.size_bytes for item in self.cache.values())
        hit_rate = (self.hits / (self.hits + self.misses)) * 100 if (self.hits + self.misses) > 0 else 0

        return {
            'name': self.name,
            'items_count': len(self.cache),
            'max_size': self.max_size,
            'total_size_bytes': total_size,
            'hits': self.hits,
            'misses': self.misses,
            'evictions': self.evictions,
            'hit_rate_percent': round(hit_rate, 2),
            'items': [
                {
                    'key': item.key,
                    'age_seconds': item.age_seconds,
                    'ttl': item.ttl,
                    'time_to_live': item.time_to_live,
                    'access_count': item.access_count,
                    'size_bytes': item.size_bytes
                }
                for item in self.cache.values()
            ]
        }

    @abstractmethod
    def get_data(self, *args, **kwargs) -> Optional[Any]:
        """Абстрактный метод получения данных с кэшированием"""
        pass


class OHLCDataCache(DataCache):
    """Кэш для OHLC данных"""

    def __init__(self):
        super().__init__(
            name='ohlc',
            max_size=CACHE_SETTINGS.get('ohlc_max_size', 500),
            default_ttl=OHLC_CACHE_TTL
        )

    def get_data(self, symbol: str, timeframe: str = '1h',
                 limit: int = 100) -> Optional[List[Dict]]:
        """Получение OHLC данных с кэшированием"""
        key = self._generate_key(symbol, timeframe, limit)
        cached = self.get(key)

        if cached:
            return cached

        # Здесь должна быть логика получения данных из API
        # Пока возвращаем None для демонстрации
        logger.debug(f"OHLC data not in cache: {symbol} {timeframe}")
        return None


class NewsDataCache(DataCache):
    """Кэш для новостных данных"""

    def __init__(self):
        super().__init__(
            name='news',
            max_size=CACHE_SETTINGS.get('news_max_size', 200),
            default_ttl=NEWS_CACHE_TTL
        )

    def get_data(self, symbol: str, limit: int = 50) -> Optional[List[Dict]]:
        """Получение новостных данных с кэшированием"""
        key = self._generate_key(symbol, limit)
        cached = self.get(key)

        if cached:
            return cached

        # Здесь должна быть логика получения новостей из API
        logger.debug(f"News data not in cache: {symbol}")
        return None


class AnomalyDataCache(DataCache):
    """Кэш для данных аномалий"""

    def __init__(self):
        super().__init__(
            name='anomaly',
            max_size=CACHE_SETTINGS.get('anomaly_max_size', 300),
            default_ttl=ANOMALY_CACHE_TTL
        )

    def get_data(self, symbol: str, days: int = 30) -> Optional[Dict]:
        """Получение данных аномалий с кэшированием"""
        key = self._generate_key(symbol, days)
        cached = self.get(key)

        if cached:
            return cached

        # Здесь должна быть логика получения данных аномалий
        logger.debug(f"Anomaly data not in cache: {symbol}")
        return None


class WhaleDataCache(DataCache):
    """Кэш для данных о китах"""

    def __init__(self):
        super().__init__(
            name='whale',
            max_size=CACHE_SETTINGS.get('whale_max_size', 100),
            default_ttl=CACHE_SETTINGS.get('whale_ttl', 1800)  # 30 минут
        )

    def get_data(self, symbol: str, min_volume: float = 1000000) -> Optional[List[Dict]]:
        """Получение данных о китовых транзакциях"""
        key = self._generate_key(symbol, min_volume)
        cached = self.get(key)

        if cached:
            return cached

        # Здесь должна быть логика получения данных о китах
        logger.debug(f"Whale data not in cache: {symbol}")
        return None


# Глобальные экземпляры кэшей
ohlc_cache = OHLCDataCache()
news_cache = NewsDataCache()
anomaly_cache = AnomalyDataCache()
whale_cache = WhaleDataCache()

# Экспорт для обратной совместимости
def cache_ohlc_data(key: str, data: Any, ttl: Optional[int] = None):
    """Обратная совместимость"""
    return ohlc_cache.set(key, data, ttl)

def get_cached_ohlc(key: str) -> Optional[Any]:
    """Обратная совместимость"""
    return ohlc_cache.get(key)
