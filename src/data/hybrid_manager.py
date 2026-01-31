#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔄 ГИБРИДНЫЙ МЕНЕДЖЕР ДАННЫХ
Умное получение данных с приоритетом свежести и кэшированием
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List
from src.utils.smart_rate_limiter import smart_rate_limiter
from src.adapters.cache import adaptive_cache

logger = logging.getLogger(__name__)

class HybridDataManager:
    """Гибридный менеджер данных с умным кэшированием"""
    
    def __init__(self):
        self.cache = adaptive_cache
        self.rate_limiter = smart_rate_limiter
        
        # Приоритеты символов
        self.symbol_priorities = {
            "critical": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
            "high": ["ADAUSDT", "SOLUSDT", "DOTUSDT", "LINKUSDT", "UNIUSDT", "SNXUSDT"],
            "medium": ["DASHUSDT", "NEARUSDT", "WIFUSDT", "AAVEUSDT"],
            "low": ["FETUSDT", "TRUMPUSDT", "ZENUSDT"]
        }
        
        # ИСПРАВЛЕНО: Расширенная статистика
        self.stats = {
            "cache_hits": 0,
            "fresh_data_requests": 0,
            "rate_limited_fallbacks": 0,
            "api_errors": 0,
            "total_requests": 0,
            "symbols_processed": 0,
            "average_response_time": 0.0,
            "last_reset": time.time()
        }
        
        # Мониторинг производительности
        self.performance_monitor = {
            "request_times": [],
            "error_counts": {},
            "symbol_usage": {}
        }
    
    def _get_symbol_priority(self, symbol: str) -> str:
        """Определяет приоритет символа"""
        for priority, symbols in self.symbol_priorities.items():
            if symbol in symbols:
                return priority
        return "low"
    
    def _get_max_age_for_priority(self, priority: str) -> float:
        """Возвращает максимальный возраст данных для приоритета"""
        max_age_rules = {
            "critical": 60,   # УВЕЛИЧЕНО: 1 минута для критических
            "high": 120,      # УВЕЛИЧЕНО: 2 минуты для высоких
            "medium": 300,    # УВЕЛИЧЕНО: 5 минут для средних
            "low": 600        # УВЕЛИЧЕНО: 10 минут для низких
        }
        return max_age_rules.get(priority, 300)
    
    async def get_smart_data(self, symbol: str, data_type: str = "ohlc", force_fresh: bool = False) -> Optional[Any]:
        """
        Умное получение данных с приоритетом свежести
        
        Args:
            symbol: Торговый символ
            data_type: Тип данных (ohlc, price, volume, etc.)
            force_fresh: Принудительно получить свежие данные
            
        Returns:
            Данные или None если недоступны
        """
        self.stats["total_requests"] += 1
        priority = self._get_symbol_priority(symbol)
        max_age = self._get_max_age_for_priority(priority)
        
        # 1. Если не требуется принудительное обновление, проверяем кэш
        if not force_fresh:
            cached_data = self.cache.get_fresh_data(symbol, data_type, max_age)
            if cached_data:
                self.stats["cache_hits"] += 1
                logger.debug("Кэш HIT для %s %s (приоритет: %s)", symbol, data_type, priority)
                return cached_data
        
        # 2. Пробуем получить свежие данные с rate limiting
        try:
            # Всегда пытаемся получить свежие данные, rate limiter сам решит когда ждать
            await self.rate_limiter.wait_for_api("binance")
            fresh_data = await self._fetch_fresh_data(symbol, data_type)
            
            if fresh_data:
                # Кэшируем свежие данные
                self.cache.set_data(symbol, data_type, fresh_data)
                self.stats["fresh_data_requests"] += 1
                logger.debug("Свежие данные для %s %s (приоритет: %s)", symbol, data_type, priority)
                return fresh_data
            else:
                # Если не получили свежие данные, используем кэш
                cached_data = self.cache.get_data(symbol, data_type)
                if cached_data:
                    self.stats["rate_limited_fallbacks"] += 1
                    logger.debug("Используем кэш для %s (свежие данные недоступны)", symbol)
                    return cached_data[0] if isinstance(cached_data, tuple) else cached_data
                
        except Exception as e:
            self.stats["api_errors"] += 1
            logger.error("Ошибка получения данных для %s: %s", symbol, e)
            
            # Fallback к кэшу при ошибке
            cached_data = self.cache.get_data(symbol, data_type)
            if cached_data:
                logger.warning("Используем кэш для %s после ошибки API", symbol)
                return cached_data[0] if isinstance(cached_data, tuple) else cached_data
        
        # 3. Если ничего не получилось
        logger.debug("Нет данных для %s %s", symbol, data_type)
        return None
    
    async def _fetch_fresh_data(self, symbol: str, data_type: str) -> Optional[Any]:
        """Получает свежие данные от API"""
        try:
            if data_type == "ohlc":
                # Импортируем функцию получения OHLC данных (синхронная)
                from src.utils.ohlc_utils import get_ohlc_binance_sync
                # Запускаем синхронную функцию в executor
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, get_ohlc_binance_sync, symbol, "1h", 300)
            elif data_type == "price":
                try:
                    from src.execution.exchange_api import get_current_price_robust
                except ImportError:
                    from improved_price_api import get_current_price_robust
                return await get_current_price_robust(symbol)
            elif data_type == "volume":
                # Заглушка для volume data
                logger.debug("Volume data not available for %s", symbol)
                return None
            else:
                logger.warning("Неизвестный тип данных: %s", data_type)
                return None
                
        except Exception as e:
            logger.error("Ошибка получения %s для %s: %s", data_type, symbol, e)
            return None
    
    async def ensure_fresh_data(self, symbol: str, data_type: str = "ohlc") -> bool:
        """
        Обеспечивает наличие свежих данных для символа
        
        Args:
            symbol: Торговый символ
            data_type: Тип данных
            
        Returns:
            True если данные свежие или обновлены, False если недоступны
        """
        # Пропускаем стейблкоины для общих обновлений данных
        try:
            from stablecoin_filter import should_skip_stablecoin
            if should_skip_stablecoin(symbol, context="data_update"):
                logger.debug("🛑 Пропуск обновления данных для стейблкоина: %s", symbol)
                return False
        except Exception:
            pass

        priority = self._get_symbol_priority(symbol)
        max_age = self._get_max_age_for_priority(priority)
        
        # Проверяем свежесть кэшированных данных
        cached_data = self.cache.get_fresh_data(symbol, data_type, max_age)
        if cached_data:
            return True
        
        # Данные устарели или отсутствуют, пытаемся обновить
        try:
            # Всегда пытаемся обновить, rate limiter сам решит когда ждать
            await self.rate_limiter.wait_for_api("binance")
            fresh_data = await self._fetch_fresh_data(symbol, data_type)
            
            if fresh_data:
                self.cache.set_data(symbol, data_type, fresh_data)
                logger.info("Обновлены данные для %s %s", symbol, data_type)
                return True
            else:
                logger.warning("Не удалось получить свежие данные для %s", symbol)
                return False
                
        except Exception as e:
            logger.error("Ошибка обновления данных для %s: %s", symbol, e)
            return False
    
    async def batch_ensure_fresh_data(self, symbols: List[str], data_type: str = "ohlc") -> Dict[str, bool]:
        """
        Пакетное обеспечение свежих данных для списка символов
        
        Args:
            symbols: Список символов
            data_type: Тип данных
            
        Returns:
            Словарь {symbol: success} для каждого символа
        """
        results = {}
        
        # Сортируем символы по приоритету
        priority_order = ["critical", "high", "medium", "low"]
        sorted_symbols = sorted(
            symbols,
            key=lambda s: priority_order.index(self._get_symbol_priority(s))
        )
        
        for symbol in sorted_symbols:
            try:
                success = await self.ensure_fresh_data(symbol, data_type)
                results[symbol] = success
                
                # УВЕЛИЧЕНА задержка между символами для оптимизации API
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error("Ошибка пакетного обновления %s: %s", symbol, e)
                results[symbol] = False
        
        return results
    
    def get_cached_data(self, symbol: str, data_type: str = "ohlc") -> Optional[Any]:
        """Быстрое получение данных из кэша без API запросов"""
        return self.cache.get_data(symbol, data_type)
    
    def invalidate_symbol(self, symbol: str) -> None:
        """Инвалидирует кэш для символа"""
        self.cache.invalidate(symbol)
        logger.info("Инвалидирован кэш для %s", symbol)
    
    def cleanup_expired(self) -> int:
        """Очищает истекшие записи из кэша"""
        return self.cache.cleanup_expired()
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику менеджера данных"""
        cache_stats = self.cache.get_stats()
        rate_limiter_stats = self.rate_limiter.get_stats()
        
        return {
            "data_manager": {
                "total_requests": self.stats["total_requests"],
                "cache_hits": self.stats["cache_hits"],
                "fresh_data_requests": self.stats["fresh_data_requests"],
                "rate_limited_fallbacks": self.stats["rate_limited_fallbacks"],
                "api_errors": self.stats["api_errors"],
                "symbols_processed": self.stats["symbols_processed"],
                "average_response_time": self.stats["average_response_time"],
                "cache_hit_rate": (self.stats["cache_hits"] / self.stats["total_requests"] * 100) if self.stats["total_requests"] > 0 else 0
            },
            "performance": {
                "request_times": self.performance_monitor["request_times"][-10:],  # Последние 10 запросов
                "error_counts": self.performance_monitor["error_counts"],
                "top_symbols": dict(sorted(self.performance_monitor["symbol_usage"].items(), 
                                         key=lambda x: x[1], reverse=True)[:10])
            },
            "cache": cache_stats,
            "rate_limiter": rate_limiter_stats
        }
    
    def get_performance_report(self) -> str:
        """ИСПРАВЛЕНО: Возвращает детальный отчет о производительности"""
        stats = self.get_stats()
        
        report = f"""
📊 ОТЧЕТ О ПРОИЗВОДИТЕЛЬНОСТИ HYBRID DATA MANAGER
================================================

🔢 СТАТИСТИКА ЗАПРОСОВ:
• Всего запросов: {stats['data_manager']['total_requests']}
• Cache hits: {stats['data_manager']['cache_hits']} ({stats['data_manager']['cache_hit_rate']:.1f}%)
• Свежие данные: {stats['data_manager']['fresh_data_requests']}
• Fallback на кэш: {stats['data_manager']['rate_limited_fallbacks']}
• Ошибки API: {stats['data_manager']['api_errors']}

⏱️ ПРОИЗВОДИТЕЛЬНОСТЬ:
• Среднее время ответа: {stats['data_manager']['average_response_time']:.2f}с
• Обработано символов: {stats['data_manager']['symbols_processed']}

📈 ТОП СИМВОЛОВ ПО ИСПОЛЬЗОВАНИЮ:
"""
        
        for symbol, count in stats['performance']['top_symbols'].items():
            report += f"• {symbol}: {count} запросов\n"
        
        if stats['performance']['error_counts']:
            report += "\n❌ ОШИБКИ ПО ТИПАМ:\n"
            for error_type, count in stats['performance']['error_counts'].items():
                report += f"• {error_type}: {count}\n"
        
        return report
    
    def reset_performance_stats(self):
        """Сбрасывает статистику производительности"""
        self.stats.update({
            "cache_hits": 0,
            "fresh_data_requests": 0,
            "rate_limited_fallbacks": 0,
            "api_errors": 0,
            "total_requests": 0,
            "symbols_processed": 0,
            "average_response_time": 0.0,
            "last_reset": time.time()
        })
        
        self.performance_monitor.update({
            "request_times": [],
            "error_counts": {},
            "symbol_usage": {}
        })
        
        logger.info("Статистика производительности сброшена")
    
    def reset_stats(self):
        """Сброс статистики"""
        self.stats = {
            "cache_hits": 0,
            "fresh_data_requests": 0,
            "rate_limited_fallbacks": 0,
            "api_errors": 0,
            "total_requests": 0
        }
        self.cache.clear()
        self.rate_limiter.reset_stats()

# Глобальный экземпляр
hybrid_data_manager = HybridDataManager()
