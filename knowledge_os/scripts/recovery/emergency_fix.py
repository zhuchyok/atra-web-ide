#!/usr/bin/env python3
"""
Экстренное исправление базы данных для системы кнопок
"""

import sqlite3
import logging
import os

def emergency_fix_database():
    """Экстренное исправление базы данных для кнопок"""
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('emergency_fix')
    
    db_path = 'trading.db'
    
    if not os.path.exists(db_path):
        logger.error(f"❌ База данных {db_path} не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("🔍 Проверяем структуру таблицы accepted_signals...")
        
        # Проверяем существование таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='accepted_signals'
        """)
        
        if not cursor.fetchone():
            logger.info("📋 Создаем таблицу accepted_signals...")
            cursor.execute("""
                CREATE TABLE accepted_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_key TEXT UNIQUE NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    signal_time DATETIME NOT NULL,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER,
                    message_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    accepted_by INTEGER,
                    accepted_time DATETIME,
                    closed_time DATETIME,
                    close_price REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("✅ Таблица accepted_signals создана")
        else:
            logger.info("📋 Таблица accepted_signals существует, проверяем структуру...")
        
        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(accepted_signals)")
        columns = [col[1] for col in cursor.fetchall()]
        
        logger.info(f"📋 Существующие колонки: {columns}")
        
        # Добавляем недостающие колонки если их нет
        if 'message_id' not in columns:
            cursor.execute("ALTER TABLE accepted_signals ADD COLUMN message_id INTEGER")
            logger.info("✅ Добавлена колонка message_id")
            
        if 'chat_id' not in columns:
            cursor.execute("ALTER TABLE accepted_signals ADD COLUMN chat_id INTEGER")
            logger.info("✅ Добавлена колонка chat_id")
        
        if 'signal_key' not in columns:
            cursor.execute("ALTER TABLE accepted_signals ADD COLUMN signal_key TEXT UNIQUE")
            logger.info("✅ Добавлена колонка signal_key")
        
        # Создаем индексы для быстрого поиска
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol_status ON accepted_signals(symbol, status)")
            logger.info("✅ Индекс idx_symbol_status создан/обновлен")
        except:
            pass
            
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signal_key ON accepted_signals(signal_key)")
            logger.info("✅ Индекс idx_signal_key создан/обновлен")
        except:
            pass
        
        # Проверяем данные
        cursor.execute("SELECT COUNT(*) FROM accepted_signals")
        count = cursor.fetchone()[0]
        logger.info(f"📊 Всего сигналов в базе: {count}")
        
        # Показываем последние сигналы
        cursor.execute("""
            SELECT symbol, status, message_id, chat_id, created_at 
            FROM accepted_signals 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        recent_signals = cursor.fetchall()
        if recent_signals:
            logger.info("📋 Последние сигналы:")
            for signal in recent_signals:
                logger.info(f"   - {signal[0]}: status={signal[1]}, msg_id={signal[2]}, chat_id={signal[3]}, time={signal[4]}")
        
        conn.commit()
        conn.close()
        
        logger.info("🎉 База данных успешно исправлена!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка исправления базы данных: {e}")
        return False

def check_database_structure():
    """Проверка структуры базы данных"""
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('db_check')
    
    db_path = 'trading.db'
    
    if not os.path.exists(db_path):
        logger.error(f"❌ База данных {db_path} не найдена!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем все таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        logger.info(f"📋 Найдено таблиц: {len(tables)}")
        for table in tables:
            logger.info(f"   - {table[0]}")
        
        # Проверяем структуру accepted_signals
        if any('accepted_signals' in table for table in tables):
            cursor.execute("PRAGMA table_info(accepted_signals)")
            columns = cursor.fetchall()
            
            logger.info("📋 Структура таблицы accepted_signals:")
            for col in columns:
                logger.info(f"   - {col[1]}: {col[2]} {'NOT NULL' if col[3] else ''} {'PRIMARY KEY' if col[5] else ''}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки базы данных: {e}")
        return False

if __name__ == "__main__":
    print("🔧 ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ БАЗЫ ДАННЫХ ДЛЯ КНОПОК")
    print("=" * 60)
    
    print("\n1. Проверка структуры базы данных...")
    check_database_structure()
    
    print("\n2. Исправление базы данных...")
    emergency_fix_database()
    
    print("\n3. Финальная проверка...")
    check_database_structure()
    
    print("\n🎉 Исправление завершено!")
