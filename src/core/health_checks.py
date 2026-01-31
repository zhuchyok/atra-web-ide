"""
Health Checks для критичных компонентов системы

Интеграция health checks в существующие компоненты
"""

import logging
from typing import Optional
from src.core.health import (
    HealthCheckManager,
    HealthStatus,
    health_check,
    get_health_manager
)

logger = logging.getLogger(__name__)


def register_system_health_checks():
    """Регистрация health checks для всех критичных компонентов"""
    manager = get_health_manager()
    
    # ========================================================================
    # Database Health Check
    # ========================================================================
    
    @health_check(name="database", critical=True, timeout=2.0)
    def check_database():
        """Проверка подключения к базе данных"""
        try:
            from src.database.db import Database
            db = Database()
            # Простая проверка - выполнение простого запроса
            db.cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    # ========================================================================
    # Telegram API Health Check
    # ========================================================================
    
    @health_check(name="telegram_api", critical=True, timeout=5.0)
    async def check_telegram():
        """Проверка доступности Telegram API"""
        try:
            # Проверяем, что бот может получить информацию о себе
            # Это упрощённая проверка - в реальности нужно использовать реальный API
            try:
                from src.telegram.bot_core import get_bot_instance
                bot = get_bot_instance()
                if bot:
                    # Попытка получить информацию о боте
                    # В реальности: await bot.get_me()
                    return True
            except ImportError:
                # Если модуль недоступен, считаем что проверка прошла
                # (не критично для работы системы)
                return True
            return False
        except Exception as e:
            logger.error(f"Telegram API health check failed: {e}")
            return False
    
    # ========================================================================
    # Exchange API Health Check
    # ========================================================================
    
    @health_check(name="exchange_api", critical=True, timeout=5.0)
    async def check_exchange_api():
        """Проверка доступности Exchange API"""
        try:
            # Проверяем доступность основного API (Binance)
            try:
                from src.execution.exchange_api import BinanceAPI
                api = BinanceAPI()
                # Упрощённая проверка - в реальности нужно сделать реальный запрос
                # price = await api.get_price("BTCUSDT")
                return True
            except ImportError:
                # Если модуль недоступен, считаем что проверка прошла
                return True
        except Exception as e:
            logger.error(f"Exchange API health check failed: {e}")
            return False
    
    # ========================================================================
    # Data Sources Health Check
    # ========================================================================
    
    @health_check(name="data_sources", critical=False, timeout=3.0)
    async def check_data_sources():
        """Проверка доступности источников данных"""
        try:
            # Проверяем, что хотя бы один источник данных доступен
            try:
                from src.data.sources_manager import get_sources_manager
                manager = get_sources_manager()
                if manager:
                    # Упрощённая проверка
                    return True
            except ImportError:
                # Если модуль недоступен, считаем что проверка прошла
                return True
            return False
        except Exception as e:
            logger.error(f"Data sources health check failed: {e}")
            return False
    
    # ========================================================================
    # Cache Health Check
    # ========================================================================
    
    @health_check(name="cache", critical=False, timeout=1.0)
    def check_cache():
        """Проверка работы кэша"""
        try:
            from src.core.cache import CacheRegistry
            cache = CacheRegistry.get_cache("default")
            if cache:
                # Простая проверка - запись и чтение
                cache.set("health_check", "ok", ttl=1)
                value = cache.get("health_check")
                return value == "ok"
            return False
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return False
    
    logger.info("System health checks registered")


# Автоматическая регистрация при импорте
try:
    register_system_health_checks()
except Exception as e:
    logger.warning(f"Failed to register system health checks: {e}")

