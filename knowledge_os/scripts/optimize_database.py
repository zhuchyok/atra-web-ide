#!/usr/bin/env python3
"""
Скрипт комплексной оптимизации базы данных.
Объединяет аудит индексов, анализ таблиц и рекомендации по оптимизации.
"""

import logging
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import Database
from src.database.index_auditor import IndexAuditor
from src.database.query_optimizer import QueryOptimizer
from src.database.table_maintenance import TableMaintenance

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Основная функция оптимизации"""
    import argparse

    parser = argparse.ArgumentParser(description="Комплексная оптимизация базы данных")
    parser.add_argument("--audit-indexes", action="store_true", help="Провести аудит индексов")
    parser.add_argument(
        "--analyze-tables", action="store_true", help="Проанализировать таблицы на фрагментацию"
    )
    parser.add_argument("--all", action="store_true", help="Выполнить все проверки")
    parser.add_argument(
        "--suggest-removals", action="store_true", help="Предложить индексы для удаления"
    )

    args = parser.parse_args()

    if not any([args.audit_indexes, args.analyze_tables, args.all]):
        args.all = True  # По умолчанию выполняем все проверки

    logger.info("🚀 Запуск комплексной оптимизации БД...")

    try:
        db = Database()

        if args.all or args.audit_indexes:
            logger.info("=" * 60)
            logger.info("📊 АУДИТ ИНДЕКСОВ")
            logger.info("=" * 60)

            auditor = IndexAuditor(db)
            audit_result = auditor.audit_indexes()

            if "error" not in audit_result:
                logger.info("Всего индексов: %d", audit_result["total_indexes"])
                logger.info("Используемых: %d", audit_result["used_indexes"])
                logger.info("Неиспользуемых: %d", audit_result["unused_indexes"])
                logger.info("Размер неиспользуемых: %.2f MB", audit_result["unused_size_mb"])

                if args.suggest_removals:
                    suggestions = auditor.suggest_index_removal()
                    if suggestions:
                        logger.info("\n💡 Предложено удалить индексы:")
                        for idx_name in suggestions:
                            logger.info("  - %s", idx_name)
                    else:
                        logger.info("\n✅ Нет индексов для удаления")

        if args.all or args.analyze_tables:
            logger.info("\n" + "=" * 60)
            logger.info("📊 АНАЛИЗ ТАБЛИЦ")
            logger.info("=" * 60)

            maintenance = TableMaintenance(db)
            analysis_result = maintenance.analyze_tables()

            if "error" not in analysis_result:
                logger.info("Всего таблиц: %d", analysis_result["total_tables"])
                logger.info("Требуют VACUUM: %d", analysis_result["tables_needing_vacuum"])
                logger.info("Общий размер: %.2f MB", analysis_result["total_size_mb"])
                logger.info("Фрагментация: %.2f%%", analysis_result["fragmentation_pct"])

                if analysis_result["recommendations"]:
                    logger.info("\n💡 Рекомендации:")
                    for rec in analysis_result["recommendations"]:
                        logger.info("  - %s", rec)

                vacuum_tables = maintenance.get_vacuum_recommendations()
                if vacuum_tables:
                    logger.info("\n📋 Таблицы для VACUUM:")
                    for table_name in vacuum_tables:
                        logger.info("  - %s", table_name)

        logger.info("\n✅ Оптимизация завершена!")
        return 0

    except Exception as e:
        logger.error("❌ Критическая ошибка оптимизации: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
