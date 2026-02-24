#!/usr/bin/env python3
"""
🧠 АДАПТИВНАЯ СИСТЕМА КЭШИРОВАНИЯ
Умное кэширование с приоритетами и TTL
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SymbolPriority(Enum):
    """Приоритеты символов"""

    CRITICAL = "critical"  # BTC, ETH, BNB
    HIGH = "high"  # Популярные альткоины
    MEDIUM = "medium"  # Обычные символы
    LOW = "low"  # Низкоприоритетные


@dataclass
class CacheEntry:
    """Запись в кэше"""

    data: Any
    timestamp: float
    priority: SymbolPriority
    access_count: int = 0
    last_access: float = 0.0


class AdaptiveCache:
    """Адаптивная система кэширования с приоритетами"""

    def __init__(self):
        self.cache: Dict[str, CacheEntry] = {}

        # TTL в зависимости от приоритета (УВЕЛИЧЕНО для оптимизации)
        self.ttl_rules = {
            SymbolPriority.CRITICAL: 60,  # УВЕЛИЧЕНО: 1 минута для критических
            SymbolPriority.HIGH: 120,  # УВЕЛИЧЕНО: 2 минуты для высоких
            SymbolPriority.MEDIUM: 300,  # УВЕЛИЧЕНО: 5 минут для средних
            SymbolPriority.LOW: 600,  # УВЕЛИЧЕНО: 10 минут для низких
        }

        # Максимальный размер кэша
        self.max_cache_size = 1000

        # Статистика
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "total_requests": 0}

    def _get_symbol_priority(self, symbol: str) -> SymbolPriority:
        """Определяет приоритет символа"""
        critical_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        high_symbols = ["ADAUSDT", "SOLUSDT", "DOTUSDT", "LINKUSDT", "UNIUSDT"]

        if symbol in critical_symbols:
            return SymbolPriority.CRITICAL
        elif symbol in high_symbols:
            return SymbolPriority.HIGH
        elif any(symbol.endswith(suffix) for suffix in ["USDT", "BUSD"]):
            return SymbolPriority.MEDIUM
        else:
            return SymbolPriority.LOW

    def _get_ttl(self, priority: SymbolPriority) -> float:
        """Возвращает TTL для приоритета"""
        return self.ttl_rules.get(priority, 120)

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Проверяет, истек ли срок действия записи"""
        ttl = self._get_ttl(entry.priority)
        return time.time() - entry.timestamp > ttl

    def _is_fresh(self, entry: CacheEntry) -> bool:
        """Проверяет свежесть записи"""
        return not self._is_expired(entry)

    def _evict_old_entries(self):
        """Удаляет старые записи при превышении лимита"""
        if len(self.cache) <= self.max_cache_size:
            return

        # Сортируем по времени последнего доступа
        sorted_entries = sorted(self.cache.items(), key=lambda x: x[1].last_access)

        # Удаляем самые старые записи
        entries_to_remove = len(self.cache) - self.max_cache_size + 10
        for i in range(entries_to_remove):
            if i < len(sorted_entries):
                symbol, _ = sorted_entries[i]
                del self.cache[symbol]
                self.stats["evictions"] += 1

    def get_data(self, symbol: str, data_type: str = "ohlc") -> Optional[Any]:
        """
        Получает данные из кэша

        Args:
            symbol: Торговый символ
            data_type: Тип данных (ohlc, price, volume, etc.)

        Returns:
            Данные или None если нет в кэше или устарели
        """
        key = f"{symbol}_{data_type}"
        self.stats["total_requests"] += 1

        if key not in self.cache:
            self.stats["misses"] += 1
            return None

        entry = self.cache[key]

        # Проверяем свежесть
        if not self._is_fresh(entry):
            del self.cache[key]
            self.stats["misses"] += 1
            logger.debug("Кэш для %s устарел, удаляем", key)
            return None

        # Обновляем статистику доступа
        entry.access_count += 1
        entry.last_access = time.time()
        self.stats["hits"] += 1

        logger.debug("Кэш HIT для %s (возраст: %.1fс)", key, time.time() - entry.timestamp)
        return entry.data

    def set_data(self, symbol: str, data_type: str, data: Any) -> None:
        """
        Сохраняет данные в кэш

        Args:
            symbol: Торговый символ
            data_type: Тип данных
            data: Данные для кэширования
        """
        key = f"{symbol}_{data_type}"
        priority = self._get_symbol_priority(symbol)

        # Создаем запись
        entry = CacheEntry(
            data=data,
            timestamp=time.time(),
            priority=priority,
            access_count=1,
            last_access=time.time(),
        )

        # Проверяем лимит размера
        if len(self.cache) >= self.max_cache_size:
            self._evict_old_entries()

        self.cache[key] = entry
        logger.debug(
            f"Кэш SET для {key} (приоритет: {priority.value}, TTL: {self._get_ttl(priority)}с)"
        )

    def get_fresh_data(
        self, symbol: str, data_type: str = "ohlc", max_age: float = 60
    ) -> Optional[Any]:
        """
        Получает свежие данные (не старше max_age секунд)

        Args:
            symbol: Торговый символ
            data_type: Тип данных
            max_age: Максимальный возраст данных в секундах

        Returns:
            Свежие данные или None
        """
        key = f"{symbol}_{data_type}"

        if key not in self.cache:
            return None

        entry = self.cache[key]
        age = time.time() - entry.timestamp

        if age <= max_age:
            entry.access_count += 1
            entry.last_access = time.time()
            self.stats["hits"] += 1
            return entry.data

        # Данные слишком старые
        self.stats["misses"] += 1
        return None

    def invalidate(self, symbol: str, data_type: str = None) -> None:
        """
        Инвалидирует кэш для символа

        Args:
            symbol: Торговый символ
            data_type: Тип данных (если None - все типы)
        """
        if data_type:
            key = f"{symbol}_{data_type}"
            if key in self.cache:
                del self.cache[key]
                logger.debug(f"Инвалидирован кэш для {key}")
        else:
            # Удаляем все записи для символа
            keys_to_remove = [key for key in self.cache.keys() if key.startswith(f"{symbol}_")]
            for key in keys_to_remove:
                del self.cache[key]
            logger.debug(f"Инвалидирован весь кэш для {symbol} ({len(keys_to_remove)} записей)")

    def cleanup_expired(self) -> int:
        """Удаляет истекшие записи из кэша"""
        expired_keys = []

        for key, entry in self.cache.items():
            if self._is_expired(entry):
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"Очищено {len(expired_keys)} истекших записей из кэша")

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кэша"""
        total_requests = self.stats["total_requests"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        # Статистика по приоритетам
        priority_stats = {}
        for priority in SymbolPriority:
            priority_entries = [
                entry for entry in self.cache.values() if entry.priority == priority
            ]
            priority_stats[priority.value] = {
                "count": len(priority_entries),
                "avg_age": sum(time.time() - entry.timestamp for entry in priority_entries)
                / len(priority_entries)
                if priority_entries
                else 0,
            }

        return {
            "cache_size": len(self.cache),
            "max_size": self.max_cache_size,
            "hit_rate_percent": hit_rate,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "evictions": self.stats["evictions"],
            "priority_stats": priority_stats,
        }

    def clear(self):
        """Очищает весь кэш"""
        self.cache.clear()
        self.stats = {"hits": 0, "misses": 0, "evictions": 0, "total_requests": 0}
        logger.info("Кэш полностью очищен")


# Глобальный экземпляр
adaptive_cache = AdaptiveCache()
