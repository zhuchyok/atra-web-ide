#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ УМНАЯ СТРАТЕГИЯ С РЕЗЕРВНЫМИ ИСТОЧНИКАМИ
Оптимизация + надежность = идеальное решение
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class DataSourceConfig:
    """Конфигурация источника данных"""
    name: str
    priority: int  # 1 = основной, 2+ = резервные
    rate_limit: int  # запросов в минуту
    reliability: float  # 0.0-1.0 (надежность)
    cost: int  # стоимость запроса (условные единицы)
    api_key: str = None  # API ключ для источника
    enabled: bool = True

@dataclass
class SymbolStrategy:
    """Стратегия получения данных для символа"""
    symbol: str
    priority: int  # 1-5 (1 = критический)
    update_interval: int  # секунды
    primary_sources: List[str]  # основные источники
    fallback_sources: List[str]  # резервные источники
    max_sources: int  # максимум источников для запроса
    cache_ttl: int  # TTL кэша в секундах
    use_fallback: bool = True  # использовать резервные при сбоях

class SmartDataStrategy:
    """Умная стратегия с резервными источниками"""
    
    def __init__(self):
        # КОНФИГУРАЦИЯ ИСТОЧНИКОВ ДАННЫХ С CRYPTORANK
        self.data_sources = {
            "binance": DataSourceConfig(
                name="Binance",
                priority=1,
                rate_limit=20,  # основной лимит
                reliability=0.95,
                cost=1
            ),
            "bybit": DataSourceConfig(
                name="Bybit", 
                priority=2,
                rate_limit=15,
                reliability=0.90,
                cost=1
            ),
            "okx": DataSourceConfig(
                name="OKX",
                priority=3,
                rate_limit=15,
                reliability=0.85,
                cost=1
            ),
            "cryptorank": DataSourceConfig(
                name="CryptoRank",
                priority=4,
                rate_limit=10,  # хороший лимит
                reliability=0.88,
                cost=1,
                api_key="fe4393f7b12dcbc09c605019e5f857922905512211eb0f6b9cc67652f2e9"
            ),
            "coingecko": DataSourceConfig(
                name="CoinGecko",
                priority=5,
                rate_limit=3,
                reliability=0.80,
                cost=2  # дороже
            ),
            "mexc": DataSourceConfig(
                name="MEXC",
                priority=6,
                rate_limit=10,
                reliability=0.75,
                cost=1
            )
        }
        
        # СТРАТЕГИИ ДЛЯ СИМВОЛОВ
        self.symbol_strategies = {
            # КРИТИЧЕСКИЕ СИМВОЛЫ (частое обновление + резервы)
            "BTCUSDT": SymbolStrategy(
                symbol="BTCUSDT",
                priority=1,
                update_interval=60,  # 1 минута
                primary_sources=["binance"],
                fallback_sources=["bybit", "okx", "cryptorank"],
                max_sources=3,  # основной + 2 резерва
                cache_ttl=30,
                use_fallback=True
            ),
            "ETHUSDT": SymbolStrategy(
                symbol="ETHUSDT",
                priority=1,
                update_interval=60,
                primary_sources=["binance"],
                fallback_sources=["bybit", "okx", "cryptorank"],
                max_sources=3,
                cache_ttl=30,
                use_fallback=True
            ),
            "BNBUSDT": SymbolStrategy(
                symbol="BNBUSDT",
                priority=1,
                update_interval=60,
                primary_sources=["binance"],
                fallback_sources=["bybit", "cryptorank"],
                max_sources=3,
                cache_ttl=30,
                use_fallback=True
            ),
            
            # ВЫСОКИЙ ПРИОРИТЕТ (среднее обновление + резервы)
            "ADAUSDT": SymbolStrategy(
                symbol="ADAUSDT",
                priority=2,
                update_interval=180,  # 3 минуты
                primary_sources=["binance"],
                fallback_sources=["bybit", "okx", "cryptorank"],
                max_sources=3,
                cache_ttl=120,
                use_fallback=True
            ),
            "SOLUSDT": SymbolStrategy(
                symbol="SOLUSDT",
                priority=2,
                update_interval=180,
                primary_sources=["binance"],
                fallback_sources=["bybit", "cryptorank"],
                max_sources=3,
                cache_ttl=120,
                use_fallback=True
            ),
            "DOTUSDT": SymbolStrategy(
                symbol="DOTUSDT",
                priority=2,
                update_interval=180,
                primary_sources=["binance"],
                fallback_sources=["okx", "cryptorank"],
                max_sources=3,
                cache_ttl=120,
                use_fallback=True
            ),
            "LINKUSDT": SymbolStrategy(
                symbol="LINKUSDT",
                priority=2,
                update_interval=180,
                primary_sources=["binance"],
                fallback_sources=["bybit", "cryptorank"],
                max_sources=3,
                cache_ttl=120,
                use_fallback=True
            ),
            
            # СРЕДНИЙ ПРИОРИТЕТ (редкое обновление + резервы)
            "UNIUSDT": SymbolStrategy(
                symbol="UNIUSDT",
                priority=3,
                update_interval=300,  # 5 минут
                primary_sources=["binance"],
                fallback_sources=["bybit"],
                max_sources=1,  # только основной
                cache_ttl=240,
                use_fallback=False  # экономим на резервах
            ),
            "SNXUSDT": SymbolStrategy(
                symbol="SNXUSDT",
                priority=3,
                update_interval=300,
                primary_sources=["binance"],
                fallback_sources=["okx"],
                max_sources=1,
                cache_ttl=240,
                use_fallback=False
            ),
            
            # НИЗКИЙ ПРИОРИТЕТ (редкое обновление, без резервов)
            "DASHUSDT": SymbolStrategy(
                symbol="DASHUSDT",
                priority=4,
                update_interval=600,  # 10 минут
                primary_sources=["binance"],
                fallback_sources=[],
                max_sources=1,
                cache_ttl=480,
                use_fallback=False
            ),
            "NEARUSDT": SymbolStrategy(
                symbol="NEARUSDT",
                priority=4,
                update_interval=600,
                primary_sources=["binance"],
                fallback_sources=[],
                max_sources=1,
                cache_ttl=480,
                use_fallback=False
            ),
            
            # ОЧЕНЬ НИЗКИЙ ПРИОРИТЕТ (очень редкое обновление)
            "WIFUSDT": SymbolStrategy(
                symbol="WIFUSDT",
                priority=5,
                update_interval=900,  # 15 минут
                primary_sources=["binance"],
                fallback_sources=[],
                max_sources=1,
                cache_ttl=720,
                use_fallback=False
            ),
            "AAVEUSDT": SymbolStrategy(
                symbol="AAVEUSDT",
                priority=5,
                update_interval=900,
                primary_sources=["binance"],
                fallback_sources=[],
                max_sources=1,
                cache_ttl=720,
                use_fallback=False
            ),
            "FETUSDT": SymbolStrategy(
                symbol="FETUSDT",
                priority=5,
                update_interval=900,
                primary_sources=["binance"],
                fallback_sources=[],
                max_sources=1,
                cache_ttl=720,
                use_fallback=False
            ),
            "TRUMPUSDT": SymbolStrategy(
                symbol="TRUMPUSDT",
                priority=5,
                update_interval=900,
                primary_sources=["binance"],
                fallback_sources=[],
                max_sources=1,
                cache_ttl=720,
                use_fallback=False
            ),
            "ZENUSDT": SymbolStrategy(
                symbol="ZENUSDT",
                priority=5,
                update_interval=900,
                primary_sources=["binance"],
                fallback_sources=[],
                max_sources=1,
                cache_ttl=720,
                use_fallback=False
            )
        }
        
        # Кэш и статистика
        self.data_cache = {}
        self.last_updates = {}
        self.source_stats = {name: {"success": 0, "errors": 0, "last_error": None} 
                           for name in self.data_sources.keys()}
    
    def calculate_optimized_requests_with_fallbacks(self) -> Dict[str, Any]:
        """Рассчитывает запросы с учетом резервных источников"""
        
        # Подсчитываем запросы по приоритетам
        requests_per_hour = {
            "critical": 0,
            "high": 0, 
            "medium": 0,
            "low": 0,
            "very_low": 0
        }
        
        # Подсчитываем по источникам
        source_requests = {name: 0 for name in self.data_sources.keys()}
        
        for symbol, strategy in self.symbol_strategies.items():
            # Основные запросы
            requests_per_hour[f"priority_{strategy.priority}"] = requests_per_hour.get(f"priority_{strategy.priority}", 0) + (3600 // strategy.update_interval)
            
            # Запросы к источникам
            for source in strategy.primary_sources:
                source_requests[source] += 3600 // strategy.update_interval
                
            # Резервные запросы (только при сбоях, примерно 10% от основных)
            if strategy.use_fallback:
                for source in strategy.fallback_sources:
                    source_requests[source] += (3600 // strategy.update_interval) // 10
        
        total_per_hour = sum(requests_per_hour.values())
        total_per_day = total_per_hour * 24
        
        return {
            "per_hour": total_per_hour,
            "per_day": total_per_day,
            "by_priority": requests_per_hour,
            "by_source": source_requests,
            "reduction_factor": 540000 / total_per_day if total_per_day > 0 else 1
        }
    
    def get_optimal_sources_for_symbol(self, symbol: str) -> List[str]:
        """Возвращает оптимальные источники для символа"""
        if symbol not in self.symbol_strategies:
            return ["binance"]  # по умолчанию
            
        strategy = self.symbol_strategies[symbol]
        
        # Сортируем источники по приоритету и надежности
        available_sources = []
        
        # Основные источники
        for source in strategy.primary_sources:
            if source in self.data_sources and self.data_sources[source].enabled:
                available_sources.append((source, 1, self.data_sources[source].reliability))
        
        # Резервные источники (только если включены)
        if strategy.use_fallback:
            for source in strategy.fallback_sources:
                if source in self.data_sources and self.data_sources[source].enabled:
                    available_sources.append((source, 2, self.data_sources[source].reliability))
        
        # Сортируем по приоритету и надежности
        available_sources.sort(key=lambda x: (x[1], -x[2]))
        
        # Возвращаем до max_sources источников
        return [source[0] for source in available_sources[:strategy.max_sources]]
    
    def should_update_symbol(self, symbol: str) -> bool:
        """Проверяет, нужно ли обновлять символ"""
        if symbol not in self.symbol_strategies:
            return False
            
        strategy = self.symbol_strategies[symbol]
        last_update = self.last_updates.get(symbol, 0)
        
        return time.time() - last_update >= strategy.update_interval
    
    def get_cache_ttl_for_symbol(self, symbol: str) -> int:
        """Возвращает TTL кэша для символа"""
        if symbol not in self.symbol_strategies:
            return 60  # по умолчанию
            
        return self.symbol_strategies[symbol].cache_ttl
    
    def update_source_stats(self, source: str, success: bool, error_msg: str = None):
        """Обновляет статистику источника"""
        if source in self.source_stats:
            if success:
                self.source_stats[source]["success"] += 1
            else:
                self.source_stats[source]["errors"] += 1
                self.source_stats[source]["last_error"] = error_msg

# Создаем экземпляр для тестирования
smart_strategy = SmartDataStrategy()

def print_smart_optimization_report():
    """Выводит отчет об умной оптимизации"""
    print("🛡️ УМНАЯ ОПТИМИЗАЦИЯ С РЕЗЕРВНЫМИ ИСТОЧНИКАМИ")
    print("="*70)
    
    # Текущие запросы
    current_requests = 540000  # в день
    
    # Оптимизированные запросы
    optimized = smart_strategy.calculate_optimized_requests_with_fallbacks()
    
    print(f"📊 ТЕКУЩИЕ ЗАПРОСЫ: {current_requests:,} в день")
    print(f"📊 ОПТИМИЗИРОВАННЫЕ: {optimized['per_day']:,} в день")
    print(f"📊 СНИЖЕНИЕ: {optimized['reduction_factor']:.1f}x")
    print(f"📊 ЭКОНОМИЯ: {current_requests - optimized['per_day']:,} запросов/день")
    
    print(f"\n📈 ПО ИСТОЧНИКАМ:")
    for source, count in optimized['by_source'].items():
        daily = count * 24
        print(f"  {source.upper()}: {count} запросов/час = {daily:,} запросов/день")
    
    print(f"\n🛡️ РЕЗЕРВНЫЕ ИСТОЧНИКИ:")
    print(f"  - Критические символы: Binance + Bybit/OKX")
    print(f"  - Высокий приоритет: Binance + резервы при сбоях")
    print(f"  - Средний приоритет: только Binance")
    print(f"  - Низкий приоритет: только Binance")
    
    print(f"\n💡 ПРЕИМУЩЕСТВА:")
    print(f"  ✅ Снижение запросов в {optimized['reduction_factor']:.1f} раз")
    print(f"  ✅ Резервные источники для критических символов")
    print(f"  ✅ Умное кэширование и приоритизация")
    print(f"  ✅ Надежность + экономия")
    
    return optimized

if __name__ == "__main__":
    print_smart_optimization_report()
