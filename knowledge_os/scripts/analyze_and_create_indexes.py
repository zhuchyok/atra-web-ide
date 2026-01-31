#!/usr/bin/env python3
"""
Скрипт для анализа медленных запросов и создания недостающих индексов.

Использует QueryProfiler для выявления медленных запросов,
анализирует планы выполнения и создает оптимальные индексы.
"""

import sqlite3
import logging
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.query_profiler import QueryProfiler, get_query_profiler
from config import DATABASE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_existing_indexes(conn: sqlite3.Connection) -> Dict[str, List[str]]:
    """Анализирует существующие индексы"""
    indexes = {}
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            m.name as table_name,
            i.name as index_name,
            i.sql as index_sql
        FROM sqlite_master i
        JOIN sqlite_master m ON i.tbl_name = m.name
        WHERE i.type = 'index'
        AND m.type = 'table'
        AND i.name NOT LIKE 'sqlite_%'
        ORDER BY m.name, i.name
    """)
    
    for row in cursor.fetchall():
        table_name, index_name, index_sql = row
        if table_name not in indexes:
            indexes[table_name] = []
        indexes[table_name].append({
            'name': index_name,
            'sql': index_sql,
        })
    
    return indexes


def suggest_indexes_for_table(table_name: str, conn: sqlite3.Connection) -> List[str]:
    """Предлагает индексы для таблицы на основе структуры"""
    suggestions = []
    
    cursor = conn.cursor()
    
    # Получаем информацию о таблице
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    # Анализируем колонки
    column_names = [col[1] for col in columns]
    
    # Предлагаем индексы на основе имен колонок
    common_index_patterns = [
        ('symbol', 'ticker'),
        ('user_id',),
        ('status',),
        ('created_at', 'timestamp', 'ts', 'time'),
        ('interval', 'timeframe'),
    ]
    
    for pattern in common_index_patterns:
        matching_cols = [col for col in column_names if any(p in col.lower() for p in pattern)]
        if matching_cols:
            # Создаем индекс на первую подходящую колонку
            col = matching_cols[0]
            index_name = f"idx_{table_name}_{col}"
            suggestions.append(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({col});")
    
    # Предлагаем составные индексы для часто используемых комбинаций
    if 'symbol' in column_names and 'interval' in column_names and 'time' in column_names:
        index_name = f"idx_{table_name}_symbol_interval_time"
        suggestions.append(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name}(symbol, interval, time);"
        )
    
    if 'user_id' in column_names and 'status' in column_names:
        index_name = f"idx_{table_name}_user_status"
        suggestions.append(
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table_name}(user_id, status);"
        )
    
    return suggestions


def create_recommended_indexes(conn: sqlite3.Connection, dry_run: bool = False):
    """Создает рекомендуемые индексы"""
    logger.info("🔍 Анализ существующих индексов...")
    existing_indexes = analyze_existing_indexes(conn)
    
    logger.info(f"📊 Найдено таблиц с индексами: {len(existing_indexes)}")
    
    # Получаем список всех таблиц
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    all_suggestions = []
    
    for table in tables:
        suggestions = suggest_indexes_for_table(table, conn)
        if suggestions:
            logger.info(f"💡 Предложения для таблицы {table}:")
            for suggestion in suggestions:
                logger.info(f"   {suggestion}")
                all_suggestions.append(suggestion)
    
    if dry_run:
        logger.info("🔍 DRY RUN: Индексы не созданы")
        return
    
    # Создаем индексы
    logger.info(f"🔧 Создание {len(all_suggestions)} индексов...")
    created = 0
    failed = 0
    
    for suggestion in all_suggestions:
        try:
            cursor.execute(suggestion)
            conn.commit()
            created += 1
            logger.info(f"✅ Создан индекс: {suggestion.split('(')[0]}")
        except sqlite3.Error as e:
            failed += 1
            logger.error(f"❌ Ошибка создания индекса: {e}")
    
    logger.info(f"✅ Создано индексов: {created}, ошибок: {failed}")


def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Анализ и создание индексов для БД')
    parser.add_argument('--db', default=DATABASE, help='Путь к файлу БД')
    parser.add_argument('--dry-run', action='store_true', help='Только показать предложения, не создавать')
    args = parser.parse_args()
    
    if not os.path.exists(args.db):
        logger.error(f"❌ Файл БД не найден: {args.db}")
        return 1
    
    try:
        conn = sqlite3.connect(args.db)
        conn.row_factory = sqlite3.Row
        
        logger.info(f"📂 Подключение к БД: {args.db}")
        
        # Анализируем и создаем индексы
        create_recommended_indexes(conn, dry_run=args.dry_run)
        
        # Показываем итоговую статистику
        existing_indexes = analyze_existing_indexes(conn)
        total_indexes = sum(len(indexes) for indexes in existing_indexes.values())
        logger.info(f"📊 Итого индексов в БД: {total_indexes}")
        
        conn.close()
        return 0
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

