#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧠 УМНЫЙ ГИБРИДНЫЙ МЕНЕДЖЕР
Интеграция умной стратегии с резервными источниками
"""

import asyncio
import time
import logging
from typing import Dict, Any, List, Optional
from smart_data_strategy import SmartDataStrategy
from smart_rate_limiter import smart_rate_limiter
from src.adapters.cache import adaptive_cache

logger = logging.getLogger(__name__)

class SmartHybridManager:
    """Умный гибридный менеджер с резервными источниками"""
    
    def __init__(self):
        self.strategy = SmartDataStrategy()
        self.rate_limiter = smart_rate_limiter
        self.cache = adaptive_cache
        
        # Статистика
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "fallback_used": 0,
            "cache_hits": 0,
            "errors": 0
        }
        
        # Кэш для данных
        self.data_cache = {}
        self.last_updates = {}
        
    async def get_smart_data(self, symbol: str, force_fresh: bool = False) -> Optional[Dict[str, Any]]:
        """Умное получение данных с резервными источниками"""
        
        # Проверяем, нужно ли обновлять
        if not force_fresh and not self.strategy.should_update_symbol(symbol):
            # Возвращаем кэшированные данные
            cached_data = self.data_cache.get(symbol)
            if cached_data:
                self.stats["cache_hits"] += 1
                logger.debug(f"📦 Кэш для {symbol}: {cached_data}")
                return cached_data
        
        # Получаем оптимальные источники
        sources = self.strategy.get_optimal_sources_for_symbol(symbol)
        
        # Пробуем источники по порядку
        for source in sources:
            try:
                # Проверяем rate limit
                if not self.rate_limiter.can_make_request(source):
                    logger.warning(f"⏳ Rate limit для {source}, пропускаем {symbol}")
                    continue
                
                # Получаем данные от источника
                data = await self._fetch_from_source(symbol, source)
                
                if data:
                    # Сохраняем в кэш
                    self.data_cache[symbol] = data
                    self.last_updates[symbol] = time.time()
                    
                    # Обновляем статистику
                    self.stats["total_requests"] += 1
                    self.stats["successful_requests"] += 1
                    
                    # Если это не основной источник, считаем как fallback
                    if source != sources[0]:
                        self.stats["fallback_used"] += 1
                        logger.info(f"🛡️ Использован резервный источник {source} для {symbol}")
                    
                    logger.info(f"✅ Данные получены для {symbol} от {source}")
                    return data
                    
            except Exception as e:
                logger.error(f"❌ Ошибка получения данных от {source} для {symbol}: {e}")
                self.stats["errors"] += 1
                continue
        
        # Если все источники не сработали
        logger.error(f"❌ Не удалось получить данные для {symbol} ни от одного источника")
        return None
    
    async def _fetch_from_source(self, symbol: str, source: str) -> Optional[Dict[str, Any]]:
        """Получает данные от конкретного источника"""
        
        # Ждем rate limit
        await self.rate_limiter.wait_for_api(source)
        
        # Получаем данные от CryptoRank
        if source == "cryptorank":
            try:
                from cryptorank_api import cryptorank_api
                data = await cryptorank_api.get_price(symbol)
                if data:
                    self.strategy.update_source_stats(source, True)
                    return data
                else:
                    self.strategy.update_source_stats(source, False)
                    return None
            except Exception as e:
                logger.error(f"Ошибка получения данных от CryptoRank для {symbol}: {e}")
                self.strategy.update_source_stats(source, False)
                return None
        
        # Для других источников - заглушка (пока)
        data = {
            "symbol": symbol,
            "price": 100.0 + hash(symbol) % 1000,  # заглушка
            "timestamp": time.time(),
            "source": source,
            "volume": 1000000,
            "change_24h": 2.5
        }
        
        # Обновляем статистику источника
        self.strategy.update_source_stats(source, True)
        
        return data
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Возвращает статистику оптимизации"""
        return {
            "strategy_stats": self.strategy.calculate_optimized_requests_with_fallbacks(),
            "manager_stats": self.stats,
            "cache_stats": {
                "size": len(self.data_cache),
                "hits": self.stats["cache_hits"]
            }
        }
    
    def print_optimization_report(self):
        """Выводит отчет об оптимизации"""
        stats = self.get_optimization_stats()
        
        print("🧠 УМНЫЙ ГИБРИДНЫЙ МЕНЕДЖЕР - ОТЧЕТ")
        print("="*60)
        
        strategy_stats = stats["strategy_stats"]
        manager_stats = stats["manager_stats"]
        
        print(f"📊 ЗАПРОСЫ В ДЕНЬ: {strategy_stats['per_day']:,}")
        print(f"📊 СНИЖЕНИЕ: {strategy_stats['reduction_factor']:.1f}x")
        
        print(f"\n📈 СТАТИСТИКА МЕНЕДЖЕРА:")
        print(f"  Всего запросов: {manager_stats['total_requests']}")
        print(f"  Успешных: {manager_stats['successful_requests']}")
        print(f"  Резервных: {manager_stats['fallback_used']}")
        print(f"  Кэш попаданий: {manager_stats['cache_hits']}")
        print(f"  Ошибок: {manager_stats['errors']}")
        
        print(f"\n🛡️ РЕЗЕРВНЫЕ ИСТОЧНИКИ:")
        for source, count in strategy_stats['by_source'].items():
            if count > 0:
                print(f"  {source.upper()}: {count} запросов/час")
        
        return stats

# Создаем глобальный экземпляр
smart_hybrid_manager = SmartHybridManager()

if __name__ == "__main__":
    smart_hybrid_manager.print_optimization_report()
