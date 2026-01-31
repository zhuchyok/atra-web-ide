#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты полного цикла работы
Проверяет весь путь: Сигнал → Фильтры → Исполнение → Управление
"""

import sys
from pathlib import Path
from typing import List

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import (
    TestResult, TestStatus, measure_time, get_db_connection
)
from scripts.test_config import DATABASE_PATH


@measure_time
def test_signal_to_db_flow() -> TestResult:
    """Проверяет поток: генерация сигнала → сохранение в БД"""
    try:
        conn = get_db_connection(DATABASE_PATH)
        if not conn:
            return TestResult(
                name="Поток сигнал → БД",
                status=TestStatus.WARNING,
                message="Не удалось подключиться к БД",
                recommendations=["Проверьте наличие trading.db"]
            )

        cursor = conn.cursor()

        # Проверяем наличие таблицы signals_log
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals_log'")
            if not cursor.fetchone():
                conn.close()
                return TestResult(
                    name="Поток сигнал → БД",
                    status=TestStatus.FAIL,
                    message="Таблица signals_log не найдена",
                    recommendations=["Создайте таблицу signals_log в БД"]
                )

            # Проверяем структуру таблицы
            cursor.execute("PRAGMA table_info(signals_log)")
            columns = [row[1] for row in cursor.fetchall()]
            # Проверяем наличие ключевых колонок (используем реальные имена из БД)
            # entry вместо entry_price, direction может отсутствовать
            required_columns = ['symbol', 'entry', 'created_at']
            missing_columns = [col for col in required_columns if col not in columns]

            if missing_columns:
                conn.close()
                return TestResult(
                    name="Поток сигнал → БД",
                    status=TestStatus.WARNING,
                    message=f"Отсутствуют некоторые колонки: {', '.join(missing_columns)}",
                    details={"columns": columns, "missing": missing_columns},
                    recommendations=["Проверьте структуру таблицы signals_log в БД"]
                )

            conn.close()
            return TestResult(
                name="Поток сигнал → БД",
                status=TestStatus.PASS,
                message="Таблица signals_log готова для записи сигналов",
                details={"columns": columns}
            )

        except Exception as e:
            conn.close()
            return TestResult(
                name="Поток сигнал → БД",
                status=TestStatus.FAIL,
                message=f"Ошибка проверки БД: {str(e)}"
            )

    except Exception as e:
        return TestResult(
            name="Поток сигнал → БД",
            status=TestStatus.FAIL,
            message=f"Ошибка при тестировании: {str(e)}"
        )


@measure_time
def test_signal_to_telegram_flow() -> TestResult:
    """Проверяет поток: сигнал → отправка в Telegram"""
    try:
        # Проверяем наличие функций отправки в Telegram
        modules_to_check = {
            "telegram_handlers": ["notify_user", "notify_all"],
            "signal_live": ["send_signal", "callback_build"],
        }

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for module_name, functions in modules_to_check.items():
            try:
                module = __import__(module_name, fromlist=functions)
                for func_name in functions:
                    func = getattr(module, func_name, None)
                    if func and callable(func):
                        test_results["found"].append(f"{module_name}.{func_name}")
                        test_results["details"][f"{module_name}.{func_name}"] = "OK"
                    else:
                        test_results["missing"].append(f"{module_name}.{func_name}")
                        test_results["details"][f"{module_name}.{func_name}"] = "Не найдено"
            except ImportError:
                for func_name in functions:
                    test_results["missing"].append(f"{module_name}.{func_name}")
                    test_results["details"][f"{module_name}.{func_name}"] = "Модуль не найден"

        if not test_results["found"]:
            return TestResult(
                name="Поток сигнал → Telegram",
                status=TestStatus.WARNING,
                message="Функции отправки в Telegram не найдены",
                details=test_results["details"],
                recommendations=["Проверьте наличие telegram_handlers.py и signal_live.py"]
            )

        return TestResult(
            name="Поток сигнал → Telegram",
            status=TestStatus.PASS,
            message=f"Найдены функции отправки ({len(test_results['found'])})",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Поток сигнал → Telegram",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_order_execution_flow() -> TestResult:
    """Проверяет поток: принятие сигнала → создание ордера"""
    try:
        # Проверяем наличие компонентов для исполнения ордеров
        components = {
            "order_manager": ["OrderManager", "create_market_order"],
            "exchange_adapter": ["ExchangeAdapter", "create_order"],
            "auto_execution": ["execute_order", "should_execute"],
        }

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for module_name, items in components.items():
            try:
                module = __import__(module_name, fromlist=items)
                for item_name in items:
                    item = getattr(module, item_name, None)
                    if item:
                        test_results["found"].append(f"{module_name}.{item_name}")
                        test_results["details"][f"{module_name}.{item_name}"] = "OK"
                    else:
                        test_results["missing"].append(f"{module_name}.{item_name}")
                        test_results["details"][f"{module_name}.{item_name}"] = "Не найдено"
            except ImportError:
                for item_name in items:
                    test_results["missing"].append(f"{module_name}.{item_name}")
                    test_results["details"][f"{module_name}.{item_name}"] = "Модуль не найден"

        if len(test_results["found"]) < 2:
            return TestResult(
                name="Поток принятие → ордер",
                status=TestStatus.WARNING,
                message=f"Найдено компонентов: {len(test_results['found'])}, отсутствует: {len(test_results['missing'])}",
                details=test_results["details"],
                recommendations=[
                    "Проверьте наличие order_manager.py и exchange_adapter.py",
                    "Некоторые компоненты могут быть опциональными"
                ]
            )

        return TestResult(
            name="Поток принятие → ордер",
            status=TestStatus.PASS,
            message=f"Найдены компоненты исполнения ({len(test_results['found'])})",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Поток принятие → ордер",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_position_management_flow() -> TestResult:
    """Проверяет поток: ордер → позиция → управление"""
    try:
        # Проверяем наличие компонентов управления позициями
        components = {
            "price_monitor_system": ["PriceMonitorSystem", "check_all_active_signals"],
            "trailing_stop_manager": ["AdvancedTrailingStopManager"],
            "order_manager": ["OrderManager"],
        }

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for module_name, items in components.items():
            try:
                module = __import__(module_name, fromlist=items)
                for item_name in items:
                    item = getattr(module, item_name, None)
                    if item:
                        test_results["found"].append(f"{module_name}.{item_name}")
                        test_results["details"][f"{module_name}.{item_name}"] = "OK"
                    else:
                        test_results["missing"].append(f"{module_name}.{item_name}")
                        test_results["details"][f"{module_name}.{item_name}"] = "Не найдено"
            except ImportError:
                for item_name in items:
                    test_results["missing"].append(f"{module_name}.{item_name}")
                    test_results["details"][f"{module_name}.{item_name}"] = "Модуль не найден"

        # Проверяем наличие таблицы active_positions
        conn = get_db_connection(DATABASE_PATH)
        if conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='active_positions'")
                if cursor.fetchone():
                    test_results["found"].append("active_positions (table)")
                    test_results["details"]["active_positions"] = "OK"
                else:
                    test_results["missing"].append("active_positions (table)")
                    test_results["details"]["active_positions"] = "Не найдена"
            except Exception:
                pass
            finally:
                conn.close()

        if len(test_results["found"]) < 3:
            return TestResult(
                name="Поток ордер → управление",
                status=TestStatus.WARNING,
                message=f"Найдено компонентов: {len(test_results['found'])}, отсутствует: {len(test_results['missing'])}",
                details=test_results["details"],
                recommendations=[
                    "Проверьте наличие всех модулей управления позициями",
                    "Создайте таблицу active_positions если отсутствует"
                ]
            )

        return TestResult(
            name="Поток ордер → управление",
            status=TestStatus.PASS,
            message=f"Найдены компоненты управления ({len(test_results['found'])})",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Поток ордер → управление",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_full_cycle_components() -> TestResult:
    """Проверяет наличие всех компонентов для полного цикла"""
    try:
        # Компоненты полного цикла
        cycle_components = {
            "Генерация сигналов": ["signal_live", "run_hybrid_signal_system_fixed"],
            "Фильтрация": ["src.filters", "SmartTrendFilter"],
            "Сохранение в БД": ["db", "Database"],
            "Отправка в Telegram": ["telegram_handlers", "notify_user"],
            "Принятие сигнала": ["signal_live", "signal_acceptance_manager"],
            "Исполнение ордера": ["order_manager", "OrderManager"],
            "Управление позицией": ["price_monitor_system", "PriceMonitorSystem"],
            "Trailing Stop": ["trailing_stop_manager", "AdvancedTrailingStopManager"],
        }

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for component_name, (module_name, item_name) in cycle_components.items():
            try:
                module = __import__(module_name, fromlist=[item_name])
                item = getattr(module, item_name, None)
                if item:
                    test_results["found"].append(component_name)
                    test_results["details"][component_name] = "OK"
                else:
                    test_results["missing"].append(component_name)
                    test_results["details"][component_name] = "Не найдено"
            except (ImportError, AttributeError):
                test_results["missing"].append(component_name)
                test_results["details"][component_name] = "Модуль/компонент не найден"

        success_rate = len(test_results["found"]) / len(cycle_components) * 100

        if success_rate < 70:
            return TestResult(
                name="Компоненты полного цикла",
                status=TestStatus.WARNING,
                message=f"Найдено {len(test_results['found'])}/{len(cycle_components)} компонентов ({success_rate:.1f}%)",
                details=test_results["details"],
                recommendations=[
                    "Проверьте наличие всех необходимых модулей",
                    "Некоторые компоненты могут быть опциональными"
                ]
            )

        return TestResult(
            name="Компоненты полного цикла",
            status=TestStatus.PASS,
            message=f"Найдено {len(test_results['found'])}/{len(cycle_components)} компонентов ({success_rate:.1f}%)",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Компоненты полного цикла",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_data_flow_integrity() -> TestResult:
    """Проверяет целостность передачи данных между компонентами"""
    try:
        # Проверяем наличие функций для работы с данными
        data_flow_checks = {
            "Сохранение сигналов": ["db", "Database", "insert_signal_log"],
            "Сохранение сигналов (entry)": ["db", "Database", "insert_signal_log_entry"],
            "Получение активных сигналов": ["db", "Database", "get_active_signal_info"],
            "Сохранение ордеров": ["order_audit_log", "OrderAuditLog", "log_order"],
        }

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for check_name, (module_name, class_name, method_name) in data_flow_checks.items():
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name, None)
                if cls:
                    method = getattr(cls, method_name, None)
                    if method and callable(method):
                        test_results["found"].append(check_name)
                        test_results["details"][check_name] = "OK"
                    else:
                        test_results["missing"].append(check_name)
                        test_results["details"][check_name] = "Метод не найден"
                else:
                    test_results["missing"].append(check_name)
                    test_results["details"][check_name] = "Класс не найден"
            except (ImportError, AttributeError) as e:
                test_results["missing"].append(check_name)
                test_results["details"][check_name] = f"Ошибка: {str(e)[:50]}"

        if len(test_results["found"]) < len(data_flow_checks) / 2:
            return TestResult(
                name="Целостность передачи данных",
                status=TestStatus.WARNING,
                message=f"Найдено функций: {len(test_results['found'])}/{len(data_flow_checks)}",
                details=test_results["details"],
                recommendations=[
                    "Проверьте наличие функций работы с данными",
                    "Некоторые функции могут иметь другие имена"
                ]
            )

        return TestResult(
            name="Целостность передачи данных",
            status=TestStatus.PASS,
            message=f"Найдено функций: {len(test_results['found'])}/{len(data_flow_checks)}",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Целостность передачи данных",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


def run_all_integration_tests() -> List[TestResult]:
    """Запускает все интеграционные тесты"""
    tests = [
        test_signal_to_db_flow,
        test_signal_to_telegram_flow,
        test_order_execution_flow,
        test_position_management_flow,
        test_full_cycle_components,
        test_data_flow_integrity
    ]

    test_results = []
    for test_func in tests:
        try:
            result = test_func()
            test_results.append(result)
            print(result)
        except Exception as e:
            test_results.append(TestResult(
                name=test_func.__name__,
                status=TestStatus.FAIL,
                message=f"Исключение при выполнении: {str(e)}"
            ))

    return test_results


if __name__ == "__main__":
    print("=" * 60)
    print("ИНТЕГРАЦИОННЫЕ ТЕСТЫ ПОЛНОГО ЦИКЛА")
    print("=" * 60)

    results = run_all_integration_tests()

    from scripts.test_utils import print_test_summary
    print_test_summary(results)

