"""
Dynamic Import Compatibility Layer
Динамический слой совместимости импортов для проекта ATRA.
Заменяет физические файлы-заглушки в корне на динамические алиасы в sys.modules.
"""

import sys
import importlib
import logging

logger = logging.getLogger(__name__)

# Карта соответствия: старое имя -> новый путь в src
IMPORT_MAP = {
    'rate_limiter': 'src.utils.rest_api_rate_limiter',
    'news_service': 'src.filters.news',
    'audit_systems': 'src.core.system_initialization',
    'forward_tester': 'src.ai.historical_analysis',
    'filter_optimizer': 'src.ai.filter_optimizer',
    'risk_manager': 'src.risk.risk_manager',
    'telegram_bot_integration': 'src.telegram.integration',
    'signal_live_integration': 'src.signals.integration',
    'system_integration': 'src.core.system_integration',
    'data_quality_monitor': 'src.monitoring.data_quality',
    'monitoring_system': 'src.monitoring.system',
    'telegram_bot': 'src.telegram.bot',
    'telegram_utils': 'src.telegram.utils',
    'telegram_handlers': 'src.telegram.handlers',
    'signal_live': 'src.signals.signal_live'
}

def setup_compatibility():
    """
    Регистрирует динамические алиасы в sys.modules.
    Позволяет делать 'import telegram_bot' даже если файла telegram_bot.py не существует.
    """
    count = 0
    for old_name, new_path in IMPORT_MAP.items():
        try:
            # Если модуль еще не загружен под старым именем
            if old_name not in sys.modules:
                # Пытаемся импортировать новый модуль
                module = importlib.import_module(new_path)
                # Регистрируем его под старым именем
                sys.modules[old_name] = module
                count += 1
        except ImportError as e:
            # logger.debug(f"Could not setup compatibility for {old_name} -> {new_path}: {e}")
            pass
    
    if count > 0:
        logger.info(f"✅ Dynamic compatibility layer initialized: {count} aliases created.")

# Автоматическая инициализация при импорте этого модуля
if __name__ != "__main__":
    setup_compatibility()

