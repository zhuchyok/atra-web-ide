#!/usr/bin/env python3
"""
Скрипт применения всех оптимизаций к базе данных.
Автоматически применяет все доступные оптимизации.
"""

import logging
import os
import sys

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db import Database
from src.database.optimization_manager import DatabaseOptimizationManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Основная функция применения оптимизаций"""
    import argparse

    parser = argparse.ArgumentParser(description="Применение всех оптимизаций к БД")
    parser.add_argument(
        "--force", action="store_true", help="Принудительное применение (даже если уже применено)"
    )
    parser.add_argument(
        "--report", action="store_true", help="Показать отчет о статусе оптимизаций"
    )
    parser.add_argument(
        "--metrics", action="store_true", help="Показать метрики производительности"
    )

    args = parser.parse_args()

    try:
        db = Database()
        manager = DatabaseOptimizationManager(db)

        if args.report or args.metrics:
            # Показываем отчет
            if args.report:
                report = manager.generate_optimization_report()
                logger.info(report)

            if args.metrics:
                metrics = manager.get_performance_metrics()
                logger.info("\n📊 МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ:")
                logger.info("=" * 60)
                for key, value in metrics.items():
                    if isinstance(value, list):
                        # TODO: Convert f-string to %s formatting for performance
                        logger.info(f"  {key}: {', '.join(value) if value else 'нет'}")
                    else:
                        # TODO: Convert f-string to %s formatting for performance
                        logger.info(f"  {key}: {value}")

            return 0

        # Применяем оптимизации
        logger.info("🚀 Применение всех оптимизаций...")

        results = manager.apply_all_optimizations(force=args.force)

        # Выводим результаты
        logger.info("=" * 60)
        logger.info("📊 РЕЗУЛЬТАТЫ ПРИМЕНЕНИЯ ОПТИМИЗАЦИЙ")
        logger.info("=" * 60)
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"✅ Успешно: {results['success_count']}")
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"❌ Ошибок: {results['failed_count']}")
        # TODO: Convert f-string to %s formatting for performance
        logger.info(f"⏱️  Время: {results['total_time']:.2f} сек")
        logger.info("")

        logger.info("Детали:")
        for opt_name, opt_result in results["optimizations"].items():
            status = opt_result.get("status", "unknown")
            icon = "✅" if status == "success" else "❌" if status == "failed" else "⏭️"
            # TODO: Convert f-string to %s formatting for performance
            logger.info(f"  {icon} {opt_name}: {status}")
            if "error" in opt_result:
                # TODO: Convert f-string to %s formatting for performance
                logger.info(f"      Ошибка: {opt_result['error']}")

        # Показываем финальный отчет
        logger.info("\n" + "=" * 60)
        report = manager.generate_optimization_report()
        logger.info(report)

        logger.info("✅ Применение оптимизаций завершено!")
        return 0

    except Exception as e:
        logger.error("❌ Критическая ошибка применения оптимизаций: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
