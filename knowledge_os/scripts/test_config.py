#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация для тестовых скриптов
"""

import os
from typing import Dict, List
from pathlib import Path

# Путь к корню проекта
PROJECT_ROOT = Path(__file__).parent.parent

# Путь к базе данных
DATABASE_PATH = os.getenv("DATABASE", "trading.db")

# Ожидаемые таблицы БД из спецификации
REQUIRED_DB_TABLES = [
    "signals_log",
    "accepted_signals",
    "rejected_signals",
    "order_audit_log",
    "active_positions",
    "filter_performance",
    "system_settings",
    "performance_metrics",
    "user_settings",
    "signal_acceptance_log"
]

# Файлы для проверки из спецификации
REQUIRED_FILES = {
    "signal_system": [
        "signal_live.py",
        "src/filters/smart_trend_filter.py",
        "src/filters/dominance_trend.py",
        "src/filters/interest_zone.py",
        "src/filters/fibonacci_zone.py",
        "src/filters/volume_imbalance.py",
        "src/filters/btc_trend.py",
        "src/filters/anomaly.py",
        "src/filters/whale.py",
        "src/filters/news.py",
        "src/strategies/adaptive_strategy.py",
        "src/analysis/pullback_entry.py",
        "src/analysis/market_structure.py"
    ],
    "order_execution": [
        "exchange_adapter.py",
        "auto_execution.py",
        "price_monitor_system.py",
        "order_manager.py",
        "order_audit_log.py"
    ],
    "risk_management": [
        "trailing_stop_manager.py",
        "price_monitor_system.py",
        "src/analysis/market_structure.py",
        "partial_profit_manager.py",
        "correlation_risk_manager.py"
    ],
    "database": [
        "db.py",
        "database_initialization.py",
        "db_health_monitor.py"
    ],
    "configuration": [
        "config.py",
        "src/core/config.py",
        "src/filters/config.py"
    ],
    "monitoring": [
        "monitoring_system.py",
        "advanced_performance_monitor.py",
        "performance_tracker.py",
        "alert_system.py",
        "alert_notifications.py"
    ]
}

# Модули для проверки импорта
REQUIRED_MODULES = {
    "signal_system": [
        ("signal_live", None),
        ("src.filters.smart_trend_filter", "SmartTrendFilter"),
        ("src.filters.dominance_trend", "DominanceTrendFilter"),
        ("src.filters.interest_zone", "InterestZoneFilter"),
        ("src.filters.fibonacci_zone", "FibonacciZoneFilter"),
        ("src.filters.volume_imbalance", "VolumeImbalanceFilter"),
        ("src.filters.btc_trend", None),
        ("src.filters.anomaly", "AnomalyFilter"),
        ("src.filters.whale", None),  # Модуль с функциями, без класса
        ("src.filters.news", None),  # Модуль с функциями, без класса
        ("src.strategies.adaptive_strategy", None),
        ("src.analysis.pullback_entry", None),
        ("src.analysis.market_structure", None)
    ],
    "order_execution": [
        ("exchange_adapter", "ExchangeAdapter"),
        ("auto_execution", None),
        ("price_monitor_system", None),
        ("order_manager", None)
    ],
    "risk_management": [
        ("trailing_stop_manager", None),
        ("partial_profit_manager", None),
        ("correlation_risk_manager", "CorrelationRiskManager")
    ],
    "database": [
        ("db", "Database"),
        ("database_initialization", None),
        ("db_health_monitor", None)
    ]
}

# Telegram токены из спецификации
TELEGRAM_TOKENS = {
    "DEV": "DEV_TOKEN_REDACTED",
    "PROD": "PROD_TOKEN_REDACTED"
}

# Конфигурационные параметры для проверки
CONFIG_PARAMETERS = {
    "USE_ADAPTIVE_STRATEGY": bool,
    "AUTO_EXECUTION_ENABLED": bool,
    "TELEGRAM_TOKEN": str,
    "BITGET_API_KEY": str,
    "BITGET_SECRET_KEY": str,
    "ATRA_ENV": str
}

# Пути к лог-файлам
LOG_PATHS = [
    "logs/signal_generation.log",
    "logs/filter_performance.log",
    "logs/order_execution.log",
    "logs/exchange_connection.log",
    "logs/trailing_stop.log",
    "logs/position_management.log",
    "bot.log",
    "main.log"
]

# Метрики для отслеживания
METRICS_TO_TRACK = {
    "signals": [
        "total_generated",
        "total_accepted",
        "total_rejected",
        "filter_pass_rate"
    ],
    "orders": [
        "total_executed",
        "successful_executions",
        "failed_executions",
        "execution_time_avg"
    ],
    "positions": [
        "active_positions",
        "positions_reached_tp1",
        "trailing_stop_activations",
        "breakeven_moves"
    ],
    "performance": [
        "signal_generation_time",
        "order_execution_time",
        "cpu_usage",
        "memory_usage"
    ]
}

# Критерии успешности
SUCCESS_CRITERIA = {
    "database": {
        "all_tables_exist": True,
        "all_tables_have_data": False,  # Не обязательно, но желательно
        "integrity_check": True
    },
    "files": {
        "all_required_files_exist": True,
        "all_modules_importable": True
    },
    "configuration": {
        "env_correctly_detected": True,
        "correct_token_used": True,
        "auto_execution_blocked_in_dev": True
    },
    "exchange": {
        "connection_successful": True,
        "api_keys_valid": False  # Опционально, может требовать реальных ключей
    },
    "logging": {
        "log_files_exist": False,  # Не обязательно при первом запуске
        "log_format_valid": True,
        "log_rotation_works": False  # Требует времени для проверки
    }
}

# Настройки отчетов
REPORT_CONFIG = {
    "output_dir": "test_reports",
    "json_report": "test_report.json",
    "markdown_report": "test_report.md",
    "console_output": True
}


# Функция get_file_path теперь в test_utils.py


def get_all_required_files() -> List[str]:
    """Получает список всех требуемых файлов"""
    all_files = []
    for category_files in REQUIRED_FILES.values():
        all_files.extend(category_files)
    return list(set(all_files))  # Убираем дубликаты


def get_all_required_modules() -> List[tuple]:
    """Получает список всех требуемых модулей"""
    all_modules = []
    for category_modules in REQUIRED_MODULES.values():
        all_modules.extend(category_modules)
    return list(set(all_modules))  # Убираем дубликаты

