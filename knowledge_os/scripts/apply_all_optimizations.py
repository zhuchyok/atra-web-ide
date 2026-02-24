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
                print(report)

            if args.metrics:
                metrics = manager.get_performance_metrics()
                print("\n📊 МЕТРИКИ ПРОИЗВОДИТЕЛЬНОСТИ:")
                print("=" * 60)
                for key, value in metrics.items():
                    if isinstance(value, list):
                        print(f"  {key}: {', '.join(value) if value else 'нет'}")
                    else:
                        print(f"  {key}: {value}")

            return 0

        # Применяем оптимизации
        logger.info("🚀 Применение всех оптимизаций...")

        results = manager.apply_all_optimizations(force=args.force)

        # Выводим результаты
        print("=" * 60)
        print("📊 РЕЗУЛЬТАТЫ ПРИМЕНЕНИЯ ОПТИМИЗАЦИЙ")
        print("=" * 60)
        print(f"✅ Успешно: {results['success_count']}")
        print(f"❌ Ошибок: {results['failed_count']}")
        print(f"⏱️  Время: {results['total_time']:.2f} сек")
        print("")

        print("Детали:")
        for opt_name, opt_result in results["optimizations"].items():
            status = opt_result.get("status", "unknown")
            icon = "✅" if status == "success" else "❌" if status == "failed" else "⏭️"
            print(f"  {icon} {opt_name}: {status}")
            if "error" in opt_result:
                print(f"      Ошибка: {opt_result['error']}")

        # Показываем финальный отчет
        print("\n" + "=" * 60)
        report = manager.generate_optimization_report()
        print(report)

        logger.info("✅ Применение оптимизаций завершено!")
        return 0

    except Exception as e:
        logger.error("❌ Критическая ошибка применения оптимизаций: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
