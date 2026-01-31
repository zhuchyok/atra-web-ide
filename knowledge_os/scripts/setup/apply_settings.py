#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 ПРИМЕНЕНИЕ УЛУЧШЕННЫХ НАСТРОЕК
Скрипт для применения более мягких настроек rate limiting
"""

import sys
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def apply_improved_rate_limits():
    """Применяет улучшенные настройки rate limiting"""
    try:
        from smart_rate_limiter import smart_rate_limiter
        
        # Обновляем лимиты для Binance
        smart_rate_limiter.api_limits["binance"].max_per_minute = 30
        smart_rate_limiter.api_limiter.api_limits["binance"].min_interval = 2.0
        
        # Обновляем лимиты для других API
        smart_rate_limiter.api_limits["bybit"].max_per_minute = 20
        smart_rate_limiter.api_limits["bybit"].min_interval = 3.0
        
        smart_rate_limiter.api_limits["okx"].max_per_minute = 20
        smart_rate_limiter.api_limits["okx"].min_interval = 3.0
        
        logger.info("✅ Улучшенные настройки rate limiting применены")
        return True
        
    except Exception as e:
        logger.error("❌ Ошибка применения улучшенных настроек: %s", e)
        return False

def apply_improved_cache_settings():
    """Применяет улучшенные настройки кэширования"""
    try:
        from adaptive_cache import adaptive_cache
        
        # Обновляем TTL правила
        adaptive_cache.ttl_rules = {
            adaptive_cache.SymbolPriority.CRITICAL: 15,  # 15 секунд
            adaptive_cache.SymbolPriority.HIGH: 30,     # 30 секунд
            adaptive_cache.SymbolPriority.MEDIUM: 60,   # 1 минута
            adaptive_cache.SymbolPriority.LOW: 180      # 3 минуты
        }
        
        logger.info("✅ Улучшенные настройки кэширования применены")
        return True
        
    except Exception as e:
        logger.error("❌ Ошибка применения настроек кэширования: %s", e)
        return False

def reset_rate_limiter_stats():
    """Сбрасывает статистику rate limiter"""
    try:
        from smart_rate_limiter import smart_rate_limiter
        smart_rate_limiter.reset_stats()
        logger.info("✅ Статистика rate limiter сброшена")
        return True
        
    except Exception as e:
        logger.error("❌ Ошибка сброса статистики: %s", e)
        return False

def main():
    """Основная функция применения улучшенных настроек"""
    logger.info("🚀 Применение улучшенных настроек гибридной системы...")
    
    success_count = 0
    total_operations = 3
    
    # 1. Применяем улучшенные настройки rate limiting
    if apply_improved_rate_limits():
        success_count += 1
    
    # 2. Применяем улучшенные настройки кэширования
    if apply_improved_cache_settings():
        success_count += 1
    
    # 3. Сбрасываем статистику
    if reset_rate_limiter_stats():
        success_count += 1
    
    # Итоговый отчет
    logger.info("\n" + "="*50)
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ")
    logger.info("="*50)
    logger.info("✅ Успешно применено: %d/%d", success_count, total_operations)
    logger.info("📊 Успешность: %.1f%%", success_count/total_operations*100)
    
    if success_count == total_operations:
        logger.info("🎉 Все улучшенные настройки применены успешно!")
        return True
    else:
        logger.warning("⚠️ Некоторые настройки не удалось применить")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
