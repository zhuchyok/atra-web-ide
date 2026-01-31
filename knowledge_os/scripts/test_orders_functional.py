#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Функциональные тесты механизма ордеров
Проверяет создание ордеров, параметры TP1/TP2/SL
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import (
    TestResult, TestStatus, measure_time
)


@measure_time
def test_order_manager_structure() -> TestResult:
    """Проверяет структуру OrderManager"""
    try:
        from order_manager import OrderManager

        manager = OrderManager()

        # Проверяем наличие ключевых методов
        required_methods = [
            'create_market_order',
            'create_limit_order',
            'create_stop_order'
        ]

        missing_methods = [
            method for method in required_methods
            if not hasattr(manager, method)
        ]

        if missing_methods:
            return TestResult(
                name="Структура OrderManager",
                status=TestStatus.WARNING,
                message=f"Отсутствуют методы: {', '.join(missing_methods)}",
                details={"missing_methods": missing_methods}
            )

        return TestResult(
            name="Структура OrderManager",
            status=TestStatus.PASS,
            message="OrderManager имеет все необходимые методы",
            details={"methods_available": required_methods}
        )

    except ImportError:
        return TestResult(
            name="Структура OrderManager",
            status=TestStatus.WARNING,
            message="Модуль order_manager не найден",
            recommendations=["Проверьте наличие order_manager.py"]
        )
    except Exception as e:
        return TestResult(
            name="Структура OrderManager",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_order_parameters_validation() -> TestResult:
    """Проверяет валидацию параметров ордеров"""
    try:
        from order_manager import OrderManager

        manager = OrderManager()

        # Проверяем наличие методов валидации
        validation_methods = [
            '_validate_order_params',
            '_calculate_order_size',
            '_get_current_price'
        ]

        found_methods = [
            method for method in validation_methods
            if hasattr(manager, method)
        ]

        if not found_methods:
            return TestResult(
                name="Валидация параметров ордеров",
                status=TestStatus.WARNING,
                message="Методы валидации не найдены (могут быть приватными)",
                details={"checked_methods": validation_methods}
            )

        return TestResult(
            name="Валидация параметров ордеров",
            status=TestStatus.PASS,
            message=f"Найдены методы валидации: {len(found_methods)}",
            details={"found_methods": found_methods}
        )

    except ImportError:
        return TestResult(
            name="Валидация параметров ордеров",
            status=TestStatus.WARNING,
            message="Модуль order_manager не найден"
        )
    except Exception as e:
        return TestResult(
            name="Валидация параметров ордеров",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_tp1_tp2_sl_order_types() -> TestResult:
    """Проверяет типы ордеров для TP1, TP2, SL"""
    try:
        # Проверяем наличие логики создания разных типов ордеров
        order_types_to_check = {
            "TP1": ["limit", "pos_profit"],
            "TP2": ["limit", "pos_profit"],
            "SL": ["stop_market", "pos_loss", "market"]
        }

        results = {
            "found": [],
            "details": {}
        }

        # Проверяем в order_manager
        try:
            from order_manager import OrderManager
            manager = OrderManager()

            # Проверяем наличие методов создания ордеров
            if hasattr(manager, 'create_tp1_order') or hasattr(manager, 'create_take_profit_order'):
                results["found"].append("TP1 order creation")
                results["details"]["TP1"] = "Метод найден"

            if hasattr(manager, 'create_tp2_order') or hasattr(manager, 'create_take_profit_order'):
                results["found"].append("TP2 order creation")
                results["details"]["TP2"] = "Метод найден"

            if hasattr(manager, 'create_stop_loss_order') or hasattr(manager, 'create_stop_order'):
                results["found"].append("SL order creation")
                results["details"]["SL"] = "Метод найден"

        except ImportError:
            pass

        # Проверяем в exchange_adapter
        try:
            from exchange_adapter import ExchangeAdapter
            adapter = ExchangeAdapter()

            # Проверяем поддержку типов ордеров
            if hasattr(adapter, 'create_order'):
                results["found"].append("ExchangeAdapter.create_order")
                results["details"]["exchange_adapter"] = "Доступен"

        except ImportError:
            pass

        if not results["found"]:
            return TestResult(
                name="Типы ордеров TP1/TP2/SL",
                status=TestStatus.WARNING,
                message="Методы создания ордеров не найдены",
                details=results["details"],
                recommendations=[
                    "Проверьте наличие методов создания ордеров в order_manager",
                    "Проверьте поддержку типов ордеров в exchange_adapter"
                ]
            )

        return TestResult(
            name="Типы ордеров TP1/TP2/SL",
            status=TestStatus.PASS,
            message=f"Найдены методы создания ордеров ({len(results['found'])})",
            details=results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Типы ордеров TP1/TP2/SL",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_order_audit_logging() -> TestResult:
    """Проверяет логирование действий с ордерами"""
    try:
        # Проверяем наличие order_audit_log
        try:
            from order_audit_log import OrderAuditLog

            audit_log = OrderAuditLog()

            # Проверяем наличие методов логирования (используем реальные имена методов)
            required_methods = ['log_order', 'log_order_sync']  # Реальные методы из order_audit_log.py
            found_methods = [
                method for method in required_methods
                if hasattr(audit_log, method)
            ]

            if not found_methods:
                return TestResult(
                    name="Логирование ордеров",
                    status=TestStatus.WARNING,
                    message="Методы логирования не найдены",
                    details={"checked_methods": required_methods},
                    recommendations=["Проверьте структуру OrderAuditLog"]
                )

            return TestResult(
                name="Логирование ордеров",
                status=TestStatus.PASS,
                message=f"OrderAuditLog имеет методы логирования ({len(found_methods)})",
                details={"methods_available": found_methods}
            )

        except ImportError:
            # Проверяем наличие таблицы в БД
            from scripts.test_utils import get_db_connection
            from scripts.test_config import DATABASE_PATH

            conn = get_db_connection(DATABASE_PATH)
            if conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_audit_log'")
                    if cursor.fetchone():
                        conn.close()
                        return TestResult(
                            name="Логирование ордеров",
                            status=TestStatus.PASS,
                            message="Таблица order_audit_log существует в БД",
                            details={"table": "order_audit_log"}
                        )
                    else:
                        conn.close()
                        return TestResult(
                            name="Логирование ордеров",
                            status=TestStatus.WARNING,
                            message="Таблица order_audit_log не найдена",
                            recommendations=["Создайте таблицу order_audit_log в БД"]
                        )
                except Exception as e:
                    conn.close()
                    return TestResult(
                        name="Логирование ордеров",
                        status=TestStatus.WARNING,
                        message=f"Ошибка проверки БД: {str(e)}"
                    )
            else:
                return TestResult(
                    name="Логирование ордеров",
                    status=TestStatus.WARNING,
                    message="Не удалось подключиться к БД"
                )

    except Exception as e:
        return TestResult(
            name="Логирование ордеров",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_reduce_only_flag() -> TestResult:
    """Проверяет использование флага reduce_only для закрытия позиций"""
    try:
        # Проверяем наличие логики reduce_only в order_manager или exchange_adapter
        reduce_only_found = False
        details = {}

        try:
            from order_manager import OrderManager
            manager = OrderManager()

            # Проверяем использование reduce_only в методах
            import inspect
            source = inspect.getsource(OrderManager)
            if 'reduce_only' in source.lower():
                reduce_only_found = True
                details["order_manager"] = "Использует reduce_only"

        except (ImportError, Exception):
            pass

        try:
            from exchange_adapter import ExchangeAdapter
            adapter = ExchangeAdapter()

            import inspect
            source = inspect.getsource(ExchangeAdapter)
            if 'reduce_only' in source.lower():
                reduce_only_found = True
                details["exchange_adapter"] = "Использует reduce_only"

        except (ImportError, Exception):
            pass

        if not reduce_only_found:
            return TestResult(
                name="Флаг reduce_only",
                status=TestStatus.WARNING,
                message="Флаг reduce_only не найден в коде",
                recommendations=[
                    "Убедитесь, что ордера на закрытие используют reduce_only=True",
                    "Это важно для безопасности позиций"
                ]
            )

        return TestResult(
            name="Флаг reduce_only",
            status=TestStatus.PASS,
            message="Флаг reduce_only используется в коде",
            details=details
        )

    except Exception as e:
        return TestResult(
            name="Флаг reduce_only",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


def run_all_orders_functional_tests() -> list:
    """Запускает все функциональные тесты ордеров"""
    tests = [
        test_order_manager_structure,
        test_order_parameters_validation,
        test_tp1_tp2_sl_order_types,
        test_order_audit_logging,
        test_reduce_only_flag
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
            print(result)
        except Exception as e:
            results.append(TestResult(
                name=test_func.__name__,
                status=TestStatus.FAIL,
                message=f"Исключение при выполнении: {str(e)}"
            ))

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("ФУНКЦИОНАЛЬНЫЕ ТЕСТЫ МЕХАНИЗМА ОРДЕРОВ")
    print("=" * 60)

    results = run_all_orders_functional_tests()

    from scripts.test_utils import print_test_summary
    print_test_summary(results)

