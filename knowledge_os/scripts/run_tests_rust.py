#!/usr/bin/env python3
"""
Rust-based Test Runner
Запуск всех тестов через Rust с многопоточностью (14 потоков по умолчанию)

ИСПОЛЬЗОВАНИЕ:
    python scripts/run_tests_rust.py                    # Все тесты, 14 потоков
    python scripts/run_tests_rust.py --threads 10       # 10 потоков
    python scripts/run_tests_rust.py --unit             # Только unit тесты
    python scripts/run_tests_rust.py --integration       # Только integration тесты
    python scripts/run_tests_rust.py tests/test_signal.py  # Конкретный тест
"""

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Динамический слой совместимости для импортов
try:
    import src.core.compat
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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


def discover_test_files(test_dir: str = "tests", pattern: str = "test_*.py") -> List[str]:
    """Обнаружить все тестовые файлы"""
    try:
        test_files = atra_rs.discover_tests(test_dir, pattern)
        logger.info("📁 Найдено %d тестовых файлов в %s", len(test_files), test_dir)
        return test_files
    except Exception as e:
        logger.error("❌ Ошибка при поиске тестов: %s", e)
        return []


def run_tests_parallel(
    test_paths: Optional[List[str]] = None,
    num_threads: int = 14,
    pytest_args: Optional[List[str]] = None,
) -> dict:
    """
    Запуск тестов через Rust с многопоточностью
    
    Args:
        test_paths: Список путей к тестам (если None - автоматический поиск)
        num_threads: Количество потоков (по умолчанию 14)
        pytest_args: Дополнительные аргументы для pytest
    
    Returns:
        Словарь с результатами выполнения
    """
    if not RUST_AVAILABLE:
        raise RuntimeError("Rust модуль atra_rs недоступен!")
    
    # Если пути не указаны, находим все тесты
    if test_paths is None:
        test_paths = discover_test_files()
        if not test_paths:
            logger.warning("⚠️ Тестовые файлы не найдены")
            return {"success": False, "error": "No test files found"}
    
    logger.info("🚀 Запуск %d тестов через Rust (%d потоков)", len(test_paths), num_threads)
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        results = atra_rs.run_tests_parallel(
            test_paths=test_paths,
            num_threads=num_threads,
            pytest_args=pytest_args
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Анализ результатов
        total = len(results)
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        errors = sum(1 for r in results if r.status == "error")
        skipped = sum(1 for r in results if r.status == "skipped")
        
        # Вывод результатов
        logger.info("=" * 80)
        logger.info("📊 РЕЗУЛЬТАТЫ ТЕСТОВ:")
        logger.info("   Всего: %d", total)
        logger.info("   ✅ Успешно: %d", passed)
        logger.info("   ❌ Провалено: %d", failed)
        logger.info("   ⚠️ Ошибки: %d", errors)
        logger.info("   ⏭️ Пропущено: %d", skipped)
        logger.info("   ⏱️ Время выполнения: %.2f сек", duration)
        logger.info("=" * 80)
        
        # Детали проваленных тестов
        if failed > 0 or errors > 0:
            logger.warning("\n❌ ПРОВАЛЕННЫЕ ТЕСТЫ:")
            for r in results:
                if r.status in ("failed", "error"):
                    logger.warning("   - %s: %s", r.name, r.status)
                    if r.error:
                        logger.warning("     Ошибка: %s", r.error[:200])
        
        return {
            "success": failed == 0 and errors == 0,
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "duration_seconds": duration,
            "results": [
                {
                    "name": r.name,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "error": r.error
                }
                for r in results
            ]
        }
        
    except Exception as e:
        logger.error("❌ Критическая ошибка при запуске тестов: %s", e)
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Запуск тестов через Rust с многопоточностью"
    )
    parser.add_argument(
        "--threads", "-t",
        type=int,
        default=14,
        help="Количество потоков (по умолчанию: 14)"
    )
    parser.add_argument(
        "--unit",
        action="store_true",
        help="Запустить только unit тесты"
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Запустить только integration тесты"
    )
    parser.add_argument(
        "--slow",
        action="store_true",
        help="Включить медленные тесты"
    )
    parser.add_argument(
        "test_paths",
        nargs="*",
        help="Конкретные пути к тестам (если не указано - все тесты)"
    )
    
    args = parser.parse_args()
    
    # Формируем pytest args
    pytest_args = []
    if args.unit:
        pytest_args.extend(["-m", "unit"])
    if args.integration:
        pytest_args.extend(["-m", "integration"])
    if not args.slow:
        pytest_args.extend(["-m", "not slow"])
    
    # Определяем пути к тестам
    test_paths = None
    if args.test_paths:
        test_paths = args.test_paths
    elif args.unit:
        test_paths = discover_test_files("tests/unit")
    elif args.integration:
        test_paths = discover_test_files("tests/integration")
    
    # Запуск тестов
    result = run_tests_parallel(
        test_paths=test_paths,
        num_threads=args.threads,
        pytest_args=pytest_args if pytest_args else None
    )
    
    # Код выхода
    sys.exit(0 if result.get("success", False) else 1)


if __name__ == "__main__":
    main()

