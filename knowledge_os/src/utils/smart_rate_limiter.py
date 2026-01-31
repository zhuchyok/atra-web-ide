#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 УМНЫЙ RATE LIMITER
Интеллектуальная система контроля частоты API запросов
"""

import asyncio
import time
import logging
from typing import Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class APILimit:
    """Конфигурация лимитов для API"""
    max_per_minute: int
    min_interval: float
    requests: int = 0
    window_start: float = 0.0
    last_request: float = 0.0

class SmartRateLimiter:
    """Умный rate limiter с адаптивными лимитами"""
    
    def __init__(self):
        # УМНЫЕ ЛИМИТЫ С РЕЗЕРВНЫМИ ИСТОЧНИКАМИ
        self.api_limits = {
            "binance": APILimit(
                max_per_minute=15,  # УМЕНЬШЕНО: Оптимизация частоты запросов
                min_interval=4.0   # УВЕЛИЧЕНО: Больше интервал между запросами
            ),
            "bybit": APILimit(
                max_per_minute=10,  # Резервный - умеренный лимит
                min_interval=6.0   # Медленнее для экономии
            ),
            "okx": APILimit(
                max_per_minute=10,  # Резервный - умеренный лимит
                min_interval=6.0   # Медленнее для экономии
            ),
            "coingecko": APILimit(
                max_per_minute=3,   # Очень консервативный
                min_interval=20.0  # 20 секунд между запросами
            ),
            "cryptorank": APILimit(
                max_per_minute=10,  # Хороший лимит для CryptoRank
                min_interval=6.0   # Умеренная скорость
            ),
            "mexc": APILimit(
                max_per_minute=5,   # Дополнительный резерв
                min_interval=12.0  # Медленные запросы
            )
        }
        
        # Статистика для мониторинга
        self.stats = {
            "total_requests": 0,
            "rate_limited_requests": 0,
            "api_errors": 0,
            "last_reset": time.time()
        }
    
    async def wait_for_api(self, api_name: str) -> bool:
        """
        Умное ожидание с учетом rate limits
        
        Args:
            api_name: Название API (binance, coingecko, etc.)
            
        Returns:
            bool: True если можно делать запрос, False если нужно подождать
        """
        if api_name not in self.api_limits:
            logger.warning("Неизвестный API: %s", api_name)
            return True
        
        api_data = self.api_limits[api_name]
        now = time.time()
        
        # 1. Проверяем минимальный интервал между запросами
        time_since_last = now - api_data.last_request
        if time_since_last < api_data.min_interval:
            wait_time = api_data.min_interval - time_since_last
            logger.debug("Rate limit %s: ждем %.1fс (min_interval)", api_name, wait_time)
            await asyncio.sleep(wait_time)
            now = time.time()
        
        # 2. Проверяем лимит запросов в минуту
        if now - api_data.window_start > 60:
            # Сброс счетчика каждую минуту
            api_data.requests = 0
            api_data.window_start = now
        
        # 3. Проверяем превышение лимита
        if api_data.requests >= api_data.max_per_minute:
            wait_time = 60 - (now - api_data.window_start)
            if wait_time > 0:
                logger.info("Rate limit %s: ждем %.1fс (max_per_minute)", api_name, wait_time)
                await asyncio.sleep(wait_time)
                # Сброс после ожидания
                api_data.requests = 0
                api_data.window_start = time.time()
                now = time.time()
        
        # 4. Обновляем статистику
        api_data.requests += 1
        api_data.last_request = now
        self.stats["total_requests"] += 1
        
        logger.debug("API %s: запрос #%d в окне", api_name, api_data.requests)
        return True
    
    def can_make_request(self, api_name: str) -> bool:
        """Проверяет, можно ли сделать запрос без ожидания"""
        if api_name not in self.api_limits:
            return True
        
        api_data = self.api_limits[api_name]
        now = time.time()
        
        # Проверяем минимальный интервал
        if now - api_data.last_request < api_data.min_interval:
            return False
        
        # Проверяем лимит в минуту
        if now - api_data.window_start > 60:
            return True  # Окно сброшено
        
        return api_data.requests < api_data.max_per_minute
    
    def get_wait_time(self, api_name: str) -> float:
        """Возвращает время ожидания для API"""
        if api_name not in self.api_limits:
            return 0.0
        
        api_data = self.api_limits[api_name]
        now = time.time()
        
        # Время до следующего запроса (min_interval)
        time_since_last = now - api_data.last_request
        min_interval_wait = max(0, api_data.min_interval - time_since_last)
        
        # Время до сброса лимита (max_per_minute)
        if api_data.requests >= api_data.max_per_minute:
            window_wait = 60 - (now - api_data.window_start)
            return max(min_interval_wait, window_wait)
        
        return min_interval_wait
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику rate limiter"""
        now = time.time()
        uptime = now - self.stats["last_reset"]
        
        return {
            "uptime_seconds": uptime,
            "total_requests": self.stats["total_requests"],
            "rate_limited_requests": self.stats["rate_limited_requests"],
            "api_errors": self.stats["api_errors"],
            "requests_per_minute": self.stats["total_requests"] / (uptime / 60) if uptime > 0 else 0,
            "api_limits": {
                name: {
                    "requests": limit.requests,
                    "max_per_minute": limit.max_per_minute,
                    "min_interval": limit.min_interval,
                    "last_request_ago": now - limit.last_request
                }
                for name, limit in self.api_limits.items()
            }
        }
    
    def reset_stats(self):
        """Сброс статистики"""
        self.stats = {
            "total_requests": 0,
            "rate_limited_requests": 0,
            "api_errors": 0,
            "last_reset": time.time()
        }
        
        # Сброс счетчиков API
        for api_data in self.api_limits.values():
            api_data.requests = 0
            api_data.window_start = time.time()
            api_data.last_request = 0.0

# Глобальный экземпляр
smart_rate_limiter = SmartRateLimiter()
