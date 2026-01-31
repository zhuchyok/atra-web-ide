#!/usr/bin/env python3
"""
Скрипт архивации старых данных.
Перемещает данные старше указанного периода в архивные таблицы.
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import Database
from src.database.archive_manager import ArchiveManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Основная функция архивации"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Архивация старых данных из БД')
    parser.add_argument(
        '--retention-days',
        type=int,
        default=730,
        help='Количество дней для хранения данных (по умолчанию 730 = 2 года)'
    )
    parser.add_argument(
        '--table',
        type=str,
        help='Конкретная таблица для архивации (если не указано, архивируются все)'
    )
    parser.add_argument(
        '--date-column',
        type=str,
        help='Колонка с датой для фильтрации (требуется с --table)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Только показать что будет заархивировано, без реальной архивации'
    )
    
    args = parser.parse_args()
    
    logger.info("🚀 Запуск архивации данных...")
    logger.info("📅 Период хранения: %d дней", args.retention_days)
    
    try:
        db = Database()
        archive_manager = ArchiveManager(db)
        
        if args.table:
            # Архивируем конкретную таблицу
            if not args.date_column:
                logger.error("❌ Требуется указать --date-column для --table")
                return 1
            
            if args.dry_run:
                logger.info("🔍 [DRY RUN] Будет заархивировано из %s", args.table)
                # Подсчитываем количество записей
                cutoff_date = datetime.now() - timedelta(days=args.retention_days)
                count_query = f"""
                    SELECT COUNT(*) FROM {args.table}
                    WHERE datetime({args.date_column}) < datetime(?)
                """
                count_result = db.execute_with_retry(
                    count_query,
                    (cutoff_date.isoformat(),),
                    is_write=False
                )
                if count_result:
                    logger.info("📊 Записей для архивации: %d", count_result[0][0])
            else:
                result = archive_manager.archive_old_data(
                    table_name=args.table,
                    date_column=args.date_column,
                    retention_days=args.retention_days
                )
                
                if result['success']:
                    logger.info(
                        "✅ Архивировано %d записей из %s",
                        result['archived_count'], args.table
                    )
                else:
                    logger.error("❌ Ошибка архивации: %s", result.get('error'))
                    return 1
        else:
            # Архивируем все таблицы
            if args.dry_run:
                logger.info("🔍 [DRY RUN] Будет заархивировано из всех таблиц")
                stats = archive_manager.get_archive_stats()
                logger.info("📊 Текущая статистика: %s", stats)
            else:
                results = archive_manager.archive_all_tables(
                    retention_days=args.retention_days
                )
                
                # Выводим результаты
                total_archived = sum(r.get('archived_count', 0) for r in results)
                successful = sum(1 for r in results if r.get('success', False))
                
                logger.info("=" * 60)
                logger.info("📊 РЕЗУЛЬТАТЫ АРХИВАЦИИ:")
                logger.info("=" * 60)
                logger.info("✅ Успешно: %d/%d таблиц", successful, len(results))
                logger.info("📦 Всего записей: %d", total_archived)
                
                for result in results:
                    if result.get('success'):
                        logger.info(
                            "  ✅ %s: %d записей",
                            result['table'], result.get('archived_count', 0)
                        )
                    else:
                        logger.warning(
                            "  ❌ %s: %s",
                            result['table'], result.get('error', 'Неизвестная ошибка')
                        )
        
        # Показываем статистику
        stats = archive_manager.get_archive_stats()
        logger.info("=" * 60)
        logger.info("📊 СТАТИСТИКА АРХИВА:")
        logger.info("=" * 60)
        logger.info("📦 Архивных таблиц: %d", len(stats['archive_tables']))
        logger.info("📊 Всего записей в архиве: %d", stats['total_archived_records'])
        logger.info("💾 Размер БД: %.2f MB", stats['active_db_size_mb'])
        
        logger.info("✅ Архивация завершена успешно!")
        return 0
        
    except Exception as e:
        logger.error("❌ Критическая ошибка архивации: %s", e, exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

