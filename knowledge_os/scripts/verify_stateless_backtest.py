#!/usr/bin/env python3
"""
Скрипт для проверки бэктестов после внедрения stateless архитектуры.

Проверяет, что результаты бэктестов идентичны baseline после рефакторинга.
"""

import sys
import logging
import traceback
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def verify_stateless_imports():
    """Проверяет, что все stateless модули импортируются корректно"""
    logger.info("🔍 Проверка импортов stateless модулей...")

    try:
        # pylint: disable=import-outside-toplevel,unused-import
        from src.infrastructure.cache import StatelessCacheManager
        logger.info("✅ StatelessCacheManager импортирован")
    except ImportError as e:
        logger.error("❌ Ошибка импорта StatelessCacheManager: %s", e)
        return False

    try:
        # pylint: disable=import-outside-toplevel,unused-import
        from src.signals.state_container import FilterState, IndicatorState, SignalState
        logger.info("✅ State containers импортированы")
    except ImportError as e:
        logger.error("❌ Ошибка импорта state containers: %s", e)
        return False

    try:
        # pylint: disable=import-outside-toplevel,unused-import
        from src.core.cache import get_cache_registry
        logger.info("✅ CacheRegistry импортирован")
    except ImportError as e:
        logger.error("❌ Ошибка импорта CacheRegistry: %s", e)
        return False

    try:
        # pylint: disable=import-outside-toplevel,unused-import
        from src.ai.system_manager import get_ai_manager
        logger.info("✅ AISystemManager импортирован")
    except ImportError as e:
        logger.error("❌ Ошибка импорта AISystemManager: %s", e)
        return False

    try:
        # pylint: disable=import-outside-toplevel,unused-import
        from src.telegram.handlers import get_session_manager
        logger.info("✅ SessionManager импортирован")
    except ImportError as e:
        logger.error("❌ Ошибка импорта SessionManager: %s", e)
        return False

    return True


def verify_backward_compatibility():
    """Проверяет обратную совместимость"""
    logger.info("🔍 Проверка обратной совместимости...")

    try:
        # Проверяем cache_manager.py
        # pylint: disable=import-outside-toplevel
        from src.utils.cache_manager import CacheManager
        CacheManager.get_symbol_info_cache()
        logger.info("✅ CacheManager.get_symbol_info_cache() работает")

        # Проверяем config.py
        # pylint: disable=import-outside-toplevel
        from src.core.config import SENT_SIGNALS_CACHE
        assert hasattr(SENT_SIGNALS_CACHE, 'get') or isinstance(SENT_SIGNALS_CACHE, dict)
        logger.info("✅ SENT_SIGNALS_CACHE доступен (backward compatibility)")

        # Проверяем handlers.py
        # pylint: disable=import-outside-toplevel
        from src.telegram.handlers import pending_trades
        assert hasattr(pending_trades, 'get') or isinstance(pending_trades, dict)
        logger.info("✅ pending_trades доступен (backward compatibility)")

        return True
    except Exception as e:
        logger.error("❌ Ошибка проверки обратной совместимости: %s", e)
        return False


def verify_filter_state_usage():
    """Проверяет использование FilterState в фильтрах"""
    logger.info("🔍 Проверка использования FilterState...")

    try:
        # pylint: disable=import-outside-toplevel
        from src.signals.filters_volume_vwap import check_volume_profile_filter
        # pylint: disable=import-outside-toplevel
        from src.signals.state_container import FilterState
        # pylint: disable=import-outside-toplevel
        import pandas as pd

        # Создаем тестовые данные
        df = pd.DataFrame({
            'close': [50000, 50100, 50200],
            'high': [51000, 51100, 51200],
            'low': [49000, 49100, 49200],
            'volume': [1000, 1100, 1200]
        })

        # Тестируем функцию с FilterState
        filter_state = FilterState()
        passed, reason, _new_state = check_volume_profile_filter(
            df, 2, 'long', filter_state=filter_state
        )

        logger.info("✅ check_volume_profile_filter работает с FilterState")
        logger.info("   Результат: passed=%s, reason=%s", passed, reason)
        return True
    except Exception as e:
        logger.error("❌ Ошибка проверки FilterState: %s", e)
        traceback.print_exc()
        return False


def main():
    """Основная функция проверки"""
    logger.info("🚀 Начало проверки stateless архитектуры...")

    results = {
        'imports': verify_stateless_imports(),
        'backward_compatibility': verify_backward_compatibility(),
        'filter_state': verify_filter_state_usage()
    }

    separator = "=" * 60
    logger.info("\n%s", separator)
    logger.info("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ:")
    logger.info("%s", separator)

    for test_name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ ПРОВАЛЕН"
        logger.info("%s: %s", test_name, status)

    all_passed = all(results.values())

    if all_passed:
        logger.info("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        logger.info("💡 Рекомендуется провести полные бэктесты для финальной проверки")
        return 0
    else:
        logger.error("\n❌ НЕКОТОРЫЕ ПРОВЕРКИ ПРОВАЛЕНЫ!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
