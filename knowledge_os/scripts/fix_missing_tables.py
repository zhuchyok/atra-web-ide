#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для создания недостающих таблиц БД
Исправление проблемы: Отсутствуют таблицы rejected_signals, filter_performance, performance_metrics, signal_acceptance_log
"""

import sqlite3
import logging
from pathlib import Path
import sys

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATABASE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_missing_tables():
    """Создает недостающие таблицы"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        logger.info("🔧 Создание недостающих таблиц...")
        
        # 1. Таблица rejected_signals
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rejected_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_price REAL,
                signal_time DATETIME NOT NULL,
                rejection_reason TEXT,
                filter_name TEXT,
                filter_result TEXT,
                signal_data TEXT, -- JSON с полными данными сигнала
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rejected_signals_symbol_time ON rejected_signals(symbol, signal_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rejected_signals_filter ON rejected_signals(filter_name)")
        logger.info("✅ Таблица rejected_signals создана")
        
        # 2. Таблица filter_performance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filter_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filter_name TEXT NOT NULL,
                symbol TEXT,
                signal_key TEXT,
                passed INTEGER DEFAULT 0, -- 0 = failed, 1 = passed
                execution_time_ms REAL,
                details TEXT, -- JSON с деталями проверки
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filter_performance_name ON filter_performance(filter_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filter_performance_passed ON filter_performance(passed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filter_performance_created ON filter_performance(created_at)")
        logger.info("✅ Таблица filter_performance создана")
        
        # 3. Таблица performance_metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                metric_type TEXT, -- 'counter', 'gauge', 'histogram'
                symbol TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT, -- JSON с дополнительными данными
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_name ON performance_metrics(metric_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp)")
        logger.info("✅ Таблица performance_metrics создана")
        
        # 4. Таблица signal_acceptance_log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_acceptance_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_key TEXT NOT NULL,
                symbol TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL, -- 'accepted', 'rejected', 'expired', 'closed'
                action_time DATETIME NOT NULL,
                entry_price REAL,
                exit_price REAL,
                pnl REAL,
                pnl_percent REAL,
                details TEXT, -- JSON с дополнительными данными
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_acceptance_log_key ON signal_acceptance_log(signal_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_acceptance_log_user ON signal_acceptance_log(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_acceptance_log_action ON signal_acceptance_log(action)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_acceptance_log_time ON signal_acceptance_log(action_time)")
        logger.info("✅ Таблица signal_acceptance_log создана")
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Все недостающие таблицы успешно созданы!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("СОЗДАНИЕ НЕДОСТАЮЩИХ ТАБЛИЦ БД")
    print("=" * 60)
    
    success = create_missing_tables()
    
    if success:
        print("\n✅ Миграция завершена успешно!")
        sys.exit(0)
    else:
        print("\n❌ Ошибка при выполнении миграции!")
        sys.exit(1)

