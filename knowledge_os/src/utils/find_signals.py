#!/usr/bin/env python3
"""
Скрипт для поиска всех мест, где хранятся сигналы
"""

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import List, Dict, Any

# Настройка логирования для CLI утилиты
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

def check_all_databases():
    """Проверяет все базы данных на наличие сигналов"""
    logger.info("🔍 ПОИСК ВСЕХ БАЗ ДАННЫХ С СИГНАЛАМИ")
    logger.info("=" * 80)
    
    # Список возможных баз данных
    db_files = [
        'trading.db',
        'acceptance.db',
        'signals.db',
        'atra.db',
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            logger.info("\n📊 Проверяем: %s", db_file)
            logger.info("-" * 80)
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # Получаем список всех таблиц
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                logger.info("   Таблицы: %s", ', '.join(tables))
                
                # Проверяем таблицы, связанные с сигналами
                signal_tables = [t for t in tables if 'signal' in t.lower()]
                
                for table in signal_tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        
                        # Получаем последние записи
                        cursor.execute(f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT 3")
                        columns = [description[0] for description in cursor.description]
                        rows = cursor.fetchall()
                        
                        logger.info("\n   📋 Таблица: %s (%d записей)", table, count)
                        if rows:
                            logger.info("   Последние записи:")
                            for i, row in enumerate(rows, 1):
                                row_dict = dict(zip(columns, row))
                                # Показываем только ключевые поля
                                if 'symbol' in row_dict:
                                    logger.info("      %d. %s | %s", i, row_dict.get('symbol', 'N/A'), row_dict.get('created_at', 'N/A'))
                                elif 'entry_time' in row_dict:
                                    logger.info("      %d. Entry: %s", i, row_dict.get('entry_time', 'N/A'))
                                else:
                                    logger.info("      %d. %s", i, str(row_dict)[:100])
                    except Exception as e:
                        logger.warning("   ⚠️ Ошибка чтения таблицы %s: %s", table, e, exc_info=True)
                
                conn.close()
            except Exception as e:
                logger.error("   ❌ Ошибка подключения к %s: %s", db_file, e, exc_info=True)

def check_signals_log_recent():
    """Проверяет signals_log на недавние сигналы"""
    logger.info("\n\n🔍 ПРОВЕРКА SIGNALS_LOG ЗА ПОСЛЕДНИЕ 2 ДНЯ")
    logger.info("=" * 80)
    
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Проверяем сигналы за последние 2 дня
        two_days_ago = (get_utc_now() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            SELECT symbol, entry, entry_time, result, created_at, user_id
            FROM signals_log 
            WHERE created_at >= ?
            ORDER BY created_at DESC
            LIMIT 20
        """, (two_days_ago,))
        
        signals = cursor.fetchall()
        
        if signals:
            logger.info("✅ Найдено %d сигналов за последние 2 дня:", len(signals))
            for i, (symbol, entry, entry_time, result, created_at, user_id) in enumerate(signals, 1):
                logger.info("   %d. %s | Entry: %s | %s | %s | User: %s", i, symbol, entry, created_at, result, user_id)
        else:
            logger.warning("❌ Нет сигналов за последние 2 дня в signals_log")
        
        conn.close()
    except Exception as e:
        logger.error("❌ Ошибка: %s", e, exc_info=True)

def check_accepted_signals_recent():
    """Проверяет accepted_signals на недавние сигналы"""
    logger.info("\n\n🔍 ПРОВЕРКА ACCEPTED_SIGNALS ЗА ПОСЛЕДНИЕ 2 ДНЯ")
    logger.info("=" * 80)
    
    try:
        # Проверяем acceptance.db
        if os.path.exists('acceptance.db'):
            conn = sqlite3.connect('acceptance.db')
            cursor = conn.cursor()
            
            two_days_ago = (get_utc_now() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute("""
                SELECT symbol, direction, entry_price, signal_time, created_at, user_id
                FROM accepted_signals 
                WHERE created_at >= ?
                ORDER BY created_at DESC
                LIMIT 20
            """, (two_days_ago,))
            
            signals = cursor.fetchall()
            
            if signals:
                logger.info("✅ Найдено %d сигналов за последние 2 дня:", len(signals))
                for i, (symbol, direction, entry_price, signal_time, created_at, user_id) in enumerate(signals, 1):
                    logger.info("   %d. %s %s | Entry: %s | %s | User: %s", i, symbol, direction, entry_price, created_at, user_id)
            else:
                logger.warning("❌ Нет сигналов за последние 2 дня в accepted_signals")
            
            conn.close()
        else:
            logger.warning("⚠️ Файл acceptance.db не найден")
    except Exception as e:
        logger.error("❌ Ошибка: %s", e, exc_info=True)

def check_specific_signals():
    """Проверяет конкретные сигналы (SUIUSDT, LINKUSDT) от 17.11.2025"""
    logger.info("\n\n🔍 ПОИСК КОНКРЕТНЫХ СИГНАЛОВ (SUIUSDT, LINKUSDT от 17.11.2025)")
    logger.info("=" * 80)
    
    target_date = "2025-11-17"
    
    # Проверяем signals_log
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT symbol, entry, entry_time, result, created_at, user_id
            FROM signals_log 
            WHERE date(created_at) = ? 
            AND symbol IN ('SUIUSDT', 'LINKUSDT')
            ORDER BY created_at DESC
        """, (target_date,))
        
        signals = cursor.fetchall()
        
        if signals:
            logger.info("✅ Найдено в signals_log: %d сигналов", len(signals))
            for symbol, entry, entry_time, result, created_at, user_id in signals:
                logger.info("   %s | Entry: %s | %s | %s", symbol, entry, created_at, result)
        else:
            logger.warning("❌ Не найдено в signals_log")
        
        conn.close()
    except Exception as e:
        logger.error("❌ Ошибка signals_log: %s", e, exc_info=True)
    
    # Проверяем accepted_signals
    try:
        if os.path.exists('acceptance.db'):
            conn = sqlite3.connect('acceptance.db')
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT symbol, direction, entry_price, signal_time, created_at, user_id
                FROM accepted_signals 
                WHERE date(created_at) = ? 
                AND symbol IN ('SUIUSDT', 'LINKUSDT')
                ORDER BY created_at DESC
            """, (target_date,))
            
            signals = cursor.fetchall()
            
            if signals:
                logger.info("✅ Найдено в accepted_signals: %d сигналов", len(signals))
                for symbol, direction, entry_price, signal_time, created_at, user_id in signals:
                    logger.info("   %s %s | Entry: %s | %s", symbol, direction, entry_price, created_at)
            else:
                logger.warning("❌ Не найдено в accepted_signals")
            
            conn.close()
    except Exception as e:
        logger.error("❌ Ошибка accepted_signals: %s", e, exc_info=True)

def main():
    """Основная функция"""
    logger.info("🔍 ПОЛНЫЙ ПОИСК МЕСТ ХРАНЕНИЯ СИГНАЛОВ")
    logger.info("=" * 80)
    
    # Проверяем все базы данных
    check_all_databases()
    
    # Проверяем signals_log
    check_signals_log_recent()
    
    # Проверяем accepted_signals
    check_accepted_signals_recent()
    
    # Проверяем конкретные сигналы
    check_specific_signals()
    
    logger.info("\n✅ Поиск завершен!")

if __name__ == "__main__":
    main()

