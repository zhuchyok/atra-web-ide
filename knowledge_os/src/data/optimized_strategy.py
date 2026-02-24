#!/usr/bin/env python3
"""
🚀 ОПТИМИЗИРОВАННАЯ СТРАТЕГИЯ ПОЛУЧЕНИЯ ДАННЫХ
Снижение API запросов в 10 раз при сохранении качества данных
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OptimizedSymbolConfig:
    """Оптимизированная конфигурация символа"""

    symbol: str
    priority: int  # 1-5 (1 = критический)
    update_interval: int  # секунды
    sources: List[str]  # приоритетные источники
    cache_ttl: int  # TTL кэша в секундах
    max_sources: int = 1  # максимум источников для запроса


class OptimizedDataStrategy:
    """Оптимизированная стратегия получения данных"""

    def __init__(self):
        # КРИТИЧЕСКИ ВАЖНЫЕ СИМВОЛЫ (обновляем часто)
        self.critical_symbols = {
            "BTCUSDT": OptimizedSymbolConfig(
                symbol="BTCUSDT",
                priority=1,
                update_interval=60,  # 1 минута вместо 30 сек
                sources=["binance"],  # только Binance
                cache_ttl=30,
                max_sources=1,
            ),
            "ETHUSDT": OptimizedSymbolConfig(
                symbol="ETHUSDT",
                priority=1,
                update_interval=60,
                sources=["binance"],
                cache_ttl=30,
                max_sources=1,
            ),
            "BNBUSDT": OptimizedSymbolConfig(
                symbol="BNBUSDT",
                priority=1,
                update_interval=60,
                sources=["binance"],
                cache_ttl=30,
                max_sources=1,
            ),
        }

        # ВЫСОКИЙ ПРИОРИТЕТ (обновляем реже)
        self.high_priority_symbols = {
            "ADAUSDT": OptimizedSymbolConfig(
                symbol="ADAUSDT",
                priority=2,
                update_interval=180,  # 3 минуты
                sources=["binance"],
                cache_ttl=120,
                max_sources=1,
            ),
            "SOLUSDT": OptimizedSymbolConfig(
                symbol="SOLUSDT",
                priority=2,
                update_interval=180,
                sources=["binance"],
                cache_ttl=120,
                max_sources=1,
            ),
            "DOTUSDT": OptimizedSymbolConfig(
                symbol="DOTUSDT",
                priority=2,
                update_interval=180,
                sources=["binance"],
                cache_ttl=120,
                max_sources=1,
            ),
            "LINKUSDT": OptimizedSymbolConfig(
                symbol="LINKUSDT",
                priority=2,
                update_interval=180,
                sources=["binance"],
                cache_ttl=120,
                max_sources=1,
            ),
        }

        # СРЕДНИЙ ПРИОРИТЕТ (обновляем еще реже)
        self.medium_priority_symbols = {
            "UNIUSDT": OptimizedSymbolConfig(
                symbol="UNIUSDT",
                priority=3,
                update_interval=300,  # 5 минут
                sources=["binance"],
                cache_ttl=240,
                max_sources=1,
            ),
            "SNXUSDT": OptimizedSymbolConfig(
                symbol="SNXUSDT",
                priority=3,
                update_interval=300,
                sources=["binance"],
                cache_ttl=240,
                max_sources=1,
            ),
        }

        # НИЗКИЙ ПРИОРИТЕТ (обновляем редко)
        self.low_priority_symbols = {
            "DASHUSDT": OptimizedSymbolConfig(
                symbol="DASHUSDT",
                priority=4,
                update_interval=600,  # 10 минут
                sources=["binance"],
                cache_ttl=480,
                max_sources=1,
            ),
            "NEARUSDT": OptimizedSymbolConfig(
                symbol="NEARUSDT",
                priority=4,
                update_interval=600,
                sources=["binance"],
                cache_ttl=480,
                max_sources=1,
            ),
        }

        # ОЧЕНЬ НИЗКИЙ ПРИОРИТЕТ (обновляем очень редко)
        self.very_low_priority_symbols = {
            "WIFUSDT": OptimizedSymbolConfig(
                symbol="WIFUSDT",
                priority=5,
                update_interval=900,  # 15 минут
                sources=["binance"],
                cache_ttl=720,
                max_sources=1,
            ),
            "AAVEUSDT": OptimizedSymbolConfig(
                symbol="AAVEUSDT",
                priority=5,
                update_interval=900,
                sources=["binance"],
                cache_ttl=720,
                max_sources=1,
            ),
            "FETUSDT": OptimizedSymbolConfig(
                symbol="FETUSDT",
                priority=5,
                update_interval=900,
                sources=["binance"],
                cache_ttl=720,
                max_sources=1,
            ),
            "TRUMPUSDT": OptimizedSymbolConfig(
                symbol="TRUMPUSDT",
                priority=5,
                update_interval=900,
                sources=["binance"],
                cache_ttl=720,
                max_sources=1,
            ),
            "ZENUSDT": OptimizedSymbolConfig(
                symbol="ZENUSDT",
                priority=5,
                update_interval=900,
                sources=["binance"],
                cache_ttl=720,
                max_sources=1,
            ),
        }

        # Объединяем все символы
        self.all_symbols = {
            **self.critical_symbols,
            **self.high_priority_symbols,
            **self.medium_priority_symbols,
            **self.low_priority_symbols,
            **self.very_low_priority_symbols,
        }

        # Кэш для данных
        self.data_cache = {}
        self.last_updates = {}

    def calculate_optimized_requests(self) -> Dict[str, int]:
        """Рассчитывает оптимизированное количество запросов"""

        # Подсчитываем запросы по приоритетам
        requests_per_hour = {
            "critical": len(self.critical_symbols) * (3600 // 60),  # каждую минуту
            "high": len(self.high_priority_symbols) * (3600 // 180),  # каждые 3 минуты
            "medium": len(self.medium_priority_symbols) * (3600 // 300),  # каждые 5 минут
            "low": len(self.low_priority_symbols) * (3600 // 600),  # каждые 10 минут
            "very_low": len(self.very_low_priority_symbols) * (3600 // 900),  # каждые 15 минут
        }

        total_per_hour = sum(requests_per_hour.values())
        total_per_day = total_per_hour * 24

        return {
            "per_hour": total_per_hour,
            "per_day": total_per_day,
            "by_priority": requests_per_hour,
            "reduction_factor": 540000 / total_per_day if total_per_day > 0 else 1,
        }

    def get_symbols_to_update(self) -> List[str]:
        """Возвращает символы, которые нужно обновить сейчас"""
        current_time = time.time()
        symbols_to_update = []

        for symbol, config in self.all_symbols.items():
            last_update = self.last_updates.get(symbol, 0)
            if current_time - last_update >= config.update_interval:
                symbols_to_update.append(symbol)

        return symbols_to_update

    async def update_symbol_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Обновляет данные для символа с оптимизацией"""
        if symbol not in self.all_symbols:
            return None

        config = self.all_symbols[symbol]

        # Проверяем кэш
        cache_key = f"{symbol}_data"
        if cache_key in self.data_cache:
            cached_data, timestamp = self.data_cache[cache_key]
            if time.time() - timestamp < config.cache_ttl:
                return cached_data

        # Получаем данные только от приоритетного источника
        try:
            # Здесь будет логика получения данных
            # Пока что возвращаем заглушку
            data = {
                "symbol": symbol,
                "price": 100.0,  # заглушка
                "timestamp": time.time(),
                "source": config.sources[0],
            }

            # Сохраняем в кэш
            self.data_cache[cache_key] = (data, time.time())
            self.last_updates[symbol] = time.time()

            return data

        except Exception as e:
            logger.error(f"Ошибка обновления {symbol}: {e}")
            return None


# Создаем экземпляр для тестирования
optimized_strategy = OptimizedDataStrategy()


def print_optimization_report():
    """Выводит отчет об оптимизации"""
    print("🚀 ОТЧЕТ ОБ ОПТИМИЗАЦИИ API ЗАПРОСОВ")
    print("=" * 60)

    # Текущие запросы
    current_requests = 540000  # в день

    # Оптимизированные запросы
    optimized = optimized_strategy.calculate_optimized_requests()

    print(f"📊 ТЕКУЩИЕ ЗАПРОСЫ: {current_requests:,} в день")
    print(f"📊 ОПТИМИЗИРОВАННЫЕ: {optimized['per_day']:,} в день")
    print(f"📊 СНИЖЕНИЕ: {optimized['reduction_factor']:.1f}x")
    print(f"📊 ЭКОНОМИЯ: {current_requests - optimized['per_day']:,} запросов/день")

    print("\n📈 ПО ПРИОРИТЕТАМ:")
    for priority, count in optimized["by_priority"].items():
        print(f"  {priority}: {count} запросов/час")

    print("\n💡 РЕКОМЕНДАЦИИ:")
    print("  - Использовать только Binance для основных символов")
    print("  - Увеличить интервалы обновления")
    print("  - Добавить умное кэширование")
    print("  - Приоритизировать критические символы")

    return optimized


if __name__ == "__main__":
    print_optimization_report()
