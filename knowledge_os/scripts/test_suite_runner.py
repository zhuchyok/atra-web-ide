#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный скрипт для запуска всех проверок
"""

import sys
import argparse
import asyncio
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

# pylint: disable=wrong-import-position
from scripts.test_utils import TestResult, TestStatus, print_test_summary, save_json_report
from scripts.test_report_generator import (
    generate_all_reports,
    generate_markdown_report,
    generate_console_report
)
from scripts.test_config import REPORT_CONFIG

# Импорт всех тестовых модулей
from scripts.test_db_structure import run_all_db_tests
from scripts.test_files_modules import run_all_file_tests
from scripts.test_configuration import run_all_config_tests
from scripts.test_exchange_connection import run_all_exchange_tests
from scripts.test_logging import run_all_logging_tests
from scripts.test_performance import run_all_performance_tests
from scripts.test_metrics import run_all_metrics_tests

# Импорт функциональных тестов
from scripts.test_signal_functional import run_all_signal_functional_tests
from scripts.test_orders_functional import run_all_orders_functional_tests
from scripts.test_risk_management_functional import run_all_risk_management_functional_tests

# Импорт интеграционных тестов и тестов алертов
from scripts.test_integration_full_cycle import run_all_integration_tests
from scripts.test_alerts_system import run_all_alerts_tests

# Импорт тестов ETH и SOL TrendFilter
from scripts.test_eth_sol_trend_filters import run_all_eth_sol_trend_tests
# pylint: enable=wrong-import-position


# Маппинг категорий на функции тестов
TEST_CATEGORIES = {
    "db": ("База данных", run_all_db_tests),
    "files": ("Файлы и модули", run_all_file_tests),
    "config": ("Конфигурация", run_all_config_tests),
    "exchange": ("Биржа", run_all_exchange_tests),
    "logging": ("Логирование", run_all_logging_tests),
    "performance": ("Производительность", run_all_performance_tests),
    "metrics": ("Метрики", run_all_metrics_tests),
    "signals_func": ("Сигналы (функциональные)", run_all_signal_functional_tests),
    "orders_func": ("Ордера (функциональные)", run_all_orders_functional_tests),
    "risk_func": ("Риски (функциональные)", run_all_risk_management_functional_tests),
    "integration": ("Интеграция (полный цикл)", run_all_integration_tests),
    "alerts": ("Система алертов", run_all_alerts_tests),
    "eth_sol_trend": ("ETH и SOL TrendFilter", run_all_eth_sol_trend_tests)
}


async def run_category_tests(category: str) -> list:
    """Запускает тесты для конкретной категории"""
    if category not in TEST_CATEGORIES:
        print(f"❌ Неизвестная категория: {category}")
        print(f"Доступные категории: {', '.join(TEST_CATEGORIES.keys())}")
        return []

    category_name, test_func = TEST_CATEGORIES[category]
    print(f"\n{'=' * 60}")
    print(f"ЗАПУСК ТЕСТОВ: {category_name}")
    print(f"{'=' * 60}\n")

    # Проверяем, является ли функция асинхронной
    if asyncio.iscoroutinefunction(test_func):
        results = await test_func()
    else:
        results = test_func()

    return results


async def run_all_tests() -> list:
    """Запускает все тесты"""
    all_results = []

    print("=" * 60)
    print("ЗАПУСК ВСЕХ ПРОВЕРОК")
    print("=" * 60)

    for _, (category_name, test_func) in TEST_CATEGORIES.items():
        print(f"\n{'=' * 60}")
        print(f"КАТЕГОРИЯ: {category_name}")
        print(f"{'=' * 60}\n")

        try:
            if asyncio.iscoroutinefunction(test_func):
                results = await test_func()
            else:
                results = test_func()

            all_results.extend(results)
        except Exception as e:
            print(f"❌ Ошибка при выполнении тестов категории {category_name}: {e}")
            all_results.append(TestResult(
                name=f"Категория {category_name}",
                status=TestStatus.FAIL,
                message=f"Исключение при выполнении: {str(e)}"
            ))

    return all_results


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Запуск тестов для торгового бота ATRA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python scripts/test_suite_runner.py --all
  python scripts/test_suite_runner.py --category db
  python scripts/test_suite_runner.py --category files --report markdown
  python scripts/test_suite_runner.py --all --report json --output-dir reports
        """
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Запустить все тесты"
    )

    parser.add_argument(
        "--category",
        type=str,
        choices=list(TEST_CATEGORIES.keys()),
        help="Запустить тесты конкретной категории"
    )

    parser.add_argument(
        "--report",
        type=str,
        choices=["json", "markdown", "console", "all"],
        default="all",
        help="Формат отчета (по умолчанию: all)"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=REPORT_CONFIG["output_dir"],
        help=f"Директория для сохранения отчетов (по умолчанию: {REPORT_CONFIG['output_dir']})"
    )

    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Не выводить отчет в консоль"
    )

    args = parser.parse_args()

    # Определяем, какие тесты запускать
    if args.all:
        results = asyncio.run(run_all_tests())
    elif args.category:
        results = asyncio.run(run_category_tests(args.category))
    else:
        parser.print_help()
        return

    if not results:
        print("❌ Не удалось выполнить тесты")
        return

    # Генерация отчетов
    print("\n" + "=" * 60)
    print("ГЕНЕРАЦИЯ ОТЧЕТОВ")
    print("=" * 60)

    # Временно отключаем консольный вывод, если указано
    if args.no_console:
        REPORT_CONFIG["console_output"] = False

    # Генерируем отчеты
    if args.report == "all":
        reports = generate_all_reports(results, args.output_dir)
    elif args.report == "json":
        json_path = f"{args.output_dir}/{REPORT_CONFIG['json_report']}"
        save_json_report(results, json_path)
        reports = {"json": json_path}
    elif args.report == "markdown":
        markdown_path = f"{args.output_dir}/{REPORT_CONFIG['markdown_report']}"
        generate_markdown_report(results, markdown_path)
        reports = {"markdown": markdown_path}
    else:  # console
        generate_console_report(results)
        reports = {"console": "stdout"}

    # Выводим информацию о созданных отчетах
    print("\n" + "=" * 60)
    print("ОТЧЕТЫ СОЗДАНЫ")
    print("=" * 60)
    for report_type, report_path in reports.items():
        print(f"{report_type.upper()}: {report_path}")

    # Итоговая статистика
    print_test_summary(results)

    # Возвращаем код выхода
    failed_count = sum(1 for r in results if r.status == TestStatus.FAIL)
    if failed_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()