#!/usr/bin/env python3
"""
Скрипт мониторинга производительности базы данных.
Отслеживает ключевые метрики и генерирует отчеты.
"""

import logging
import os
import sys
from datetime import datetime, timedelta

from src.shared.utils.datetime_utils import get_utc_now

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import Database
from src.database.optimization_manager import DatabaseOptimizationManager
from src.database.query_profiler import get_query_profiler

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def format_size(size_bytes):
    """Форматирует размер в читаемый формат"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"


def get_table_sizes(db):
    """Получает размеры всех таблиц"""
    sizes = {}
    try:
        tables = db.execute_with_retry(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
            (),
            is_write=False,
        )

        for (table_name,) in tables:
            try:
                # Получаем количество строк
                count = db.execute_with_retry(
                    f"SELECT COUNT(*) FROM {table_name}", (), is_write=False
                )
                row_count = count[0][0] if count else 0

                # Получаем размер страниц (приблизительно)
                page_info = db.execute_with_retry("PRAGMA page_count", (), is_write=False)

                sizes[table_name] = {
                    "row_count": row_count,
                    "estimated_size_mb": 0,  # Будет рассчитано позже
                }
            except Exception as e:
                logger.warning(f"⚠️ Ошибка получения размера таблицы {table_name}: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка получения размеров таблиц: {e}")

    return sizes


def get_index_usage(db):
    """Получает информацию об использовании индексов"""
    try:
        from src.database.index_auditor import IndexAuditor

        auditor = IndexAuditor(db)
        # Получаем список всех индексов
        all_indexes = auditor.list_indexes()
        # Проверяем использование (упрощенная версия)
        # В реальности нужен более детальный анализ
        return {
            "total_indexes": len(all_indexes) if all_indexes else 0,
            "unused_count": 0,  # Требует детального анализа
            "unused_indexes": [],
        }
    except Exception as e:
        logger.warning(f"⚠️ Ошибка получения информации об индексах: {e}")
        return {"total_indexes": 0, "unused_count": 0, "unused_indexes": []}


def get_slow_queries_stats(profiler):
    """Получает статистику медленных запросов"""
    try:
        # Получаем статистику из профилировщика
        # (требует реализации метода get_stats в QueryProfiler)
        return {"total_slow_queries": 0, "avg_execution_time": 0.0, "max_execution_time": 0.0}
    except Exception as e:
        logger.warning(f"⚠️ Ошибка получения статистики запросов: {e}")
        return {"total_slow_queries": 0, "avg_execution_time": 0.0, "max_execution_time": 0.0}


def generate_performance_report(db, manager):
    """Генерирует отчет о производительности"""
    import os

    report = []
    report.append("=" * 70)
    report.append("📊 ОТЧЕТ О ПРОИЗВОДИТЕЛЬНОСТИ БАЗЫ ДАННЫХ")
    report.append("=" * 70)
    report.append(f"Дата: {get_utc_now().isoformat()}")
    report.append("")

    # Общие метрики
    metrics = manager.get_performance_metrics()
    report.append("📈 ОБЩИЕ МЕТРИКИ:")
    report.append("-" * 70)
    report.append(f"  • Размер БД: {format_size(metrics['database_size_mb'] * 1024 * 1024)}")
    report.append(f"  • Таблиц: {metrics['table_count']}")
    report.append(f"  • Индексов: {metrics['index_count']}")
    report.append("")

    # Статус оптимизаций
    status = manager.get_optimization_status()
    report.append("✅ СТАТУС ОПТИМИЗАЦИЙ:")
    report.append("-" * 70)
    applied = sum(1 for v in status.values() if v)
    total = len(status)
    report.append(f"  Применено: {applied}/{total}")
    report.append("")

    # Размеры таблиц (топ 10)
    table_sizes = get_table_sizes(db)
    if table_sizes:
        report.append("📋 РАЗМЕРЫ ТАБЛИЦ (ТОП 10):")
        report.append("-" * 70)
        sorted_tables = sorted(table_sizes.items(), key=lambda x: x[1]["row_count"], reverse=True)[
            :10
        ]
        for table_name, info in sorted_tables:
            report.append(f"  • {table_name}: {info['row_count']:,} строк")
        report.append("")

    # Использование индексов
    index_usage = get_index_usage(db)
    if index_usage["total_indexes"] > 0:
        report.append("📊 ИНФОРМАЦИЯ ОБ ИНДЕКСАХ:")
        report.append("-" * 70)
        report.append(f"  • Всего индексов: {index_usage['total_indexes']}")
        if index_usage["unused_count"] > 0:
            report.append(f"  ⚠️ Неиспользуемых: {index_usage['unused_count']}")
            if index_usage["unused_indexes"]:
                report.append("  Примеры:")
                for idx in index_usage["unused_indexes"][:5]:
                    report.append(f"    • {idx}")
            report.append("")
            report.append(
                "  💡 Рекомендация: запустите python3 scripts/optimize_database.py --audit-indexes"
            )
        report.append("")

    # Рекомендации
    report.append("💡 РЕКОМЕНДАЦИИ:")
    report.append("-" * 70)

    if metrics["database_size_mb"] > 100:
        report.append("  ⚠️ Размер БД > 100 MB - рассмотрите архивацию старых данных")
        report.append("     python3 scripts/archive_old_data.py")

    if index_usage.get("unused_count", 0) > 5:
        report.append("  ⚠️ Много неиспользуемых индексов - рассмотрите их удаление")
        report.append(
            "     python3 scripts/optimize_database.py --audit-indexes --suggest-removals"
        )

    if applied < total:
        report.append("  ⚠️ Не все оптимизации применены - примените их:")
        report.append("     python3 scripts/apply_all_optimizations.py")

    if not any(
        [metrics["database_size_mb"] > 100, index_usage["unused_count"] > 5, applied < total]
    ):
        report.append("  ✅ Все в порядке! Продолжайте регулярное обслуживание.")

    report.append("")
    report.append("=" * 70)

    return "\n".join(report)


def main():
    """Основная функция"""
    import argparse

    parser = argparse.ArgumentParser(description="Мониторинг производительности БД")
    parser.add_argument(
        "--output", type=str, help="Файл для сохранения отчета (по умолчанию - вывод в консоль)"
    )
    parser.add_argument(
        "--watch", action="store_true", help="Непрерывный мониторинг (обновление каждые 60 сек)"
    )

    args = parser.parse_args()

    try:
        db = Database()
        manager = DatabaseOptimizationManager(db)
        profiler = get_query_profiler()

        if args.watch:
            import time

            logger.info("🔄 Запуск непрерывного мониторинга (Ctrl+C для остановки)...")
            try:
                while True:
                    report = generate_performance_report(db, manager)
                    os.system("clear" if os.name != "nt" else "cls")
                    print(report)
                    print("\n⏳ Ожидание 60 секунд... (Ctrl+C для остановки)")
                    time.sleep(60)
            except KeyboardInterrupt:
                logger.info("✅ Мониторинг остановлен")
        else:
            report = generate_performance_report(db, manager)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(report)
                logger.info(f"✅ Отчет сохранен в {args.output}")
            else:
                print(report)

        return 0

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
