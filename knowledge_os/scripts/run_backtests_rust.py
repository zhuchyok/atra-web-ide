#!/usr/bin/env python3
"""
Rust-based Backtest Runner
Запуск всех бэктестов через Rust с многопоточностью (14 потоков по умолчанию)

ИСПОЛЬЗОВАНИЕ:
    python scripts/run_backtests_rust.py                    # Все бэктесты, 14 потоков
    python scripts/run_backtests_rust.py --threads 10       # 10 потоков
    python scripts/run_backtests_rust.py --scripts          # Только scripts/backtest*.py
    python scripts/run_backtests_rust.py scripts/backtest_5coins_intelligent.py  # Конкретный бэктест
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Динамический слой совместимости для импортов
try:
    import src.core.compat
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

try:
    import atra_rs

    RUST_AVAILABLE = True
    logger.info("✅ Rust модуль atra_rs доступен")
except ImportError:
    RUST_AVAILABLE = False
    logger.error("❌ Rust модуль atra_rs недоступен! Установите Rust модуль:")
    logger.error("   cd rust-atra && cargo build --release")
    sys.exit(1)


def discover_backtest_files(
    backtest_dirs: Optional[List[str]] = None, pattern: str = "backtest*.py"
) -> List[str]:
    """Обнаружить все бэктест скрипты"""
    if backtest_dirs is None:
        backtest_dirs = ["scripts", "backtests"]

    try:
        backtest_files = atra_rs.discover_backtests(backtest_dirs, pattern)
        logger.info("📁 Найдено %d бэктест скриптов", len(backtest_files))
        return backtest_files
    except Exception as e:
        logger.error("❌ Ошибка при поиске бэктестов: %s", e)
        return []


def run_backtests_parallel(
    backtest_scripts: Optional[List[str]] = None,
    num_threads: int = 14,
    python_args: Optional[List[str]] = None,
) -> dict:
    """
    Запуск бэктестов через Rust с многопоточностью

    Args:
        backtest_scripts: Список путей к бэктестам (если None - автоматический поиск)
        num_threads: Количество потоков (по умолчанию 14)
        python_args: Дополнительные аргументы для Python

    Returns:
        Словарь с результатами выполнения
    """
    if not RUST_AVAILABLE:
        raise RuntimeError("Rust модуль atra_rs недоступен!")

    # Если скрипты не указаны, находим все бэктесты
    if backtest_scripts is None:
        backtest_scripts = discover_backtest_files()
        if not backtest_scripts:
            logger.warning("⚠️ Бэктест скрипты не найдены")
            return {"success": False, "error": "No backtest scripts found"}

        logger.info(
            "🚀 Запуск %d бэктестов через Rust (%d потоков)", len(backtest_scripts), num_threads
        )
    logger.info("=" * 80)

    start_time = datetime.now()

    try:
        results = atra_rs.run_backtests_parallel(
            backtest_scripts=backtest_scripts, num_threads=num_threads, python_args=python_args
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Анализ результатов
        total = len(results)
        completed = sum(1 for r in results if r.status == "completed")
        failed = sum(1 for r in results if r.status == "failed")
        errors = sum(1 for r in results if r.status == "error")

        # Вывод результатов
        logger.info("=" * 80)
        logger.info("📊 РЕЗУЛЬТАТЫ БЭКТЕСТОВ:")
        logger.info("   Всего: %d", total)
        logger.info("   ✅ Завершено: %d", completed)
        logger.info("   ❌ Провалено: %d", failed)
        logger.info("   ⚠️ Ошибки: %d", errors)
        logger.info("   ⏱️ Время выполнения: %.2f сек", duration)
        logger.info("=" * 80)

        # Детали проваленных бэктестов
        if failed > 0 or errors > 0:
            logger.warning("\n❌ ПРОВАЛЕННЫЕ БЭКТЕСТЫ:")
            for r in results:
                if r.status in ("failed", "error"):
                    logger.warning("   - %s: %s", r.script, r.status)
                    if r.error:
                        logger.warning("     Ошибка: %s", r.error[:200])

        # Детали успешных бэктестов
        if completed > 0:
            logger.info("\n✅ УСПЕШНЫЕ БЭКТЕСТЫ:")
            for r in results:
                if r.status == "completed":
                    logger.info("   - %s: %dms", r.script, r.duration_ms)

        return {
            "success": failed == 0 and errors == 0,
            "total": total,
            "completed": completed,
            "failed": failed,
            "errors": errors,
            "duration_seconds": duration,
            "results": [
                {
                    "script": r.script,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in results
            ],
        }

    except Exception as e:
        logger.error("❌ Критическая ошибка при запуске бэктестов: %s", e)
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description="Запуск бэктестов через Rust с многопоточностью")
    parser.add_argument(
        "--threads", "-t", type=int, default=14, help="Количество потоков (по умолчанию: 14)"
    )
    parser.add_argument(
        "--scripts", action="store_true", help="Искать только в scripts/ директории"
    )
    parser.add_argument(
        "--backtests", action="store_true", help="Искать только в backtests/ директории"
    )
    parser.add_argument(
        "backtest_scripts",
        nargs="*",
        help="Конкретные пути к бэктестам (если не указано - все бэктесты)",
    )

    args = parser.parse_args()

    # Определяем пути к бэктестам
    backtest_scripts = None
    if args.backtest_scripts:
        backtest_scripts = args.backtest_scripts
    else:
        backtest_dirs = []
        if args.scripts:
            backtest_dirs.append("scripts")
        elif args.backtests:
            backtest_dirs.append("backtests")
        else:
            backtest_dirs = ["scripts", "backtests"]

        backtest_scripts = discover_backtest_files(backtest_dirs)

    # Запуск бэктестов
    result = run_backtests_parallel(backtest_scripts=backtest_scripts, num_threads=args.threads)

    # Код выхода
    sys.exit(0 if result.get("success", False) else 1)


if __name__ == "__main__":
    main()
