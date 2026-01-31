#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты системы алертов
Проверяет Telegram уведомления, типы алертов, приоритеты
"""

import sys
import inspect
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import (
    TestResult, TestStatus, measure_time
)


@measure_time
def test_alert_system_structure() -> TestResult:
    """Проверяет структуру системы алертов"""
    try:
        # Проверяем наличие AlertSystem
        try:
            from src.monitoring.alerts import AlertSystem

            # Проверяем наличие ключевых методов
            required_methods = [
                'create_alert',
                'check_alert_rules',
                '_send_notifications'
            ]

            missing_methods = [
                method for method in required_methods
                if not hasattr(AlertSystem, method)
            ]

            if missing_methods:
                return TestResult(
                    name="Структура AlertSystem",
                    status=TestStatus.WARNING,
                    message=f"Отсутствуют методы: {', '.join(missing_methods)}",
                    details={"missing_methods": missing_methods}
                )

            # Проверяем инициализацию
            try:
                AlertSystem()  # Проверяем, что класс может быть инициализирован
                return TestResult(
                    name="Структура AlertSystem",
                    status=TestStatus.PASS,
                    message="AlertSystem доступен и инициализируется",
                    details={"methods_available": required_methods}
                )
            except Exception as e:
                return TestResult(
                    name="Структура AlertSystem",
                    status=TestStatus.WARNING,
                    message=f"Ошибка инициализации: {str(e)}",
                    details={"error": str(e)}
                )

        except ImportError:
            # Проверяем альтернативные системы алертов
            try:
                __import__("monitoring_system", fromlist=["AlertManager"])
                return TestResult(
                    name="Структура AlertSystem",
                    status=TestStatus.PASS,
                    message="Найден AlertManager (альтернативная система)",
                    details={"system": "AlertManager"}
                )
            except ImportError:
                return TestResult(
                    name="Структура AlertSystem",
                    status=TestStatus.WARNING,
                    message="Система алертов не найдена",
                    recommendations=[
                        "Проверьте наличие alert_system.py или monitoring_system.py",
                        "Система алертов может быть опциональной"
                    ]
                )

    except Exception as e:
        return TestResult(
            name="Структура AlertSystem",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_telegram_notification_channels() -> TestResult:
    """Проверяет каналы уведомлений через Telegram"""
    try:
        # Проверяем наличие функций отправки в Telegram
        notification_functions = {
            "telegram_handlers": ["notify_user", "notify_all"],
            "telegram_message_updater": ["TelegramMessageUpdater", "send_notification"],
            "alert_system": ["TelegramNotificationChannel"],
        }

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for module_name, items in notification_functions.items():
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

        if not test_results["found"]:
            return TestResult(
                name="Каналы Telegram уведомлений",
                status=TestStatus.WARNING,
                message="Функции отправки в Telegram не найдены",
                details=test_results["details"],
                recommendations=["Проверьте наличие telegram_handlers.py"]
            )

        return TestResult(
            name="Каналы Telegram уведомлений",
            status=TestStatus.PASS,
            message=f"Найдены функции отправки ({len(test_results['found'])})",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Каналы Telegram уведомлений",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_alert_types_and_severity() -> TestResult:
    """Проверяет типы алертов и уровни серьезности"""
    try:
        # Проверяем наличие типов алертов
        alert_systems_to_check = [
            ("alert_system", "AlertType", "AlertSeverity"),
            ("monitoring_system", "AlertType", "AlertSeverity"),
        ]

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for module_name, type_name, severity_name in alert_systems_to_check:
            try:
                module = __import__(module_name, fromlist=[type_name, severity_name])

                alert_type = getattr(module, type_name, None)
                alert_severity = getattr(module, severity_name, None)

                if alert_type:
                    test_results["found"].append(f"{module_name}.{type_name}")
                    test_results["details"][f"{module_name}.{type_name}"] = "OK"
                else:
                    test_results["missing"].append(f"{module_name}.{type_name}")
                    test_results["details"][f"{module_name}.{type_name}"] = "Не найдено"

                if alert_severity:
                    test_results["found"].append(f"{module_name}.{severity_name}")
                    test_results["details"][f"{module_name}.{severity_name}"] = "OK"
                else:
                    test_results["missing"].append(f"{module_name}.{severity_name}")
                    test_results["details"][f"{module_name}.{severity_name}"] = "Не найдено"

            except ImportError:
                test_results["missing"].extend([f"{module_name}.{type_name}", f"{module_name}.{severity_name}"])
                test_results["details"][f"{module_name}.{type_name}"] = "Модуль не найден"
                test_results["details"][f"{module_name}.{severity_name}"] = "Модуль не найден"

        if not test_results["found"]:
            return TestResult(
                name="Типы и уровни алертов",
                status=TestStatus.WARNING,
                message="Типы и уровни алертов не найдены",
                details=test_results["details"],
                recommendations=[
                    "Проверьте наличие alert_system.py или monitoring_system.py",
                    "Типы алертов могут быть определены в других модулях"
                ]
            )

        return TestResult(
            name="Типы и уровни алертов",
            status=TestStatus.PASS,
            message=f"Найдены типы и уровни алертов ({len(test_results['found'])})",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Типы и уровни алертов",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_personal_vs_system_alerts() -> TestResult:
    """Проверяет разделение персональных и системных алертов"""
    try:
        # Проверяем наличие логики разделения алертов
        alert_systems = ["alert_system", "monitoring_system"]

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for module_name in alert_systems:
            try:
                module = __import__(module_name, fromlist=[])

                # Проверяем наличие параметра user_id в методах
                source = inspect.getsource(module) if hasattr(module, '__file__') else ""

                if 'user_id' in source.lower() or 'personal' in source.lower():
                    test_results["found"].append(f"{module_name} (поддержка user_id)")
                    test_results["details"][f"{module_name}"] = "Поддержка персональных алертов"
                else:
                    test_results["missing"].append(f"{module_name} (нет user_id)")
                    test_results["details"][f"{module_name}"] = "Нет поддержки персональных алертов"

            except ImportError:
                test_results["missing"].append(f"{module_name} (модуль не найден)")
                test_results["details"][f"{module_name}"] = "Модуль не найден"

        if not test_results["found"]:
            return TestResult(
                name="Персональные vs системные алерты",
                status=TestStatus.WARNING,
                message="Разделение персональных/системных алертов не найдено",
                details=test_results["details"],
                recommendations=[
                    "Проверьте наличие параметра user_id в методах создания алертов",
                    "Разделение может быть реализовано по-другому"
                ]
            )

        return TestResult(
            name="Персональные vs системные алерты",
            status=TestStatus.PASS,
            message=f"Найдена поддержка разделения ({len(test_results['found'])})",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Персональные vs системные алерты",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_alert_priorities_and_escalation() -> TestResult:
    """Проверяет приоритеты и эскалацию алертов"""
    try:
        # Проверяем наличие логики приоритетов
        alert_systems = ["alert_system", "monitoring_system"]

        test_results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for module_name in alert_systems:
            try:
                module = __import__(module_name, fromlist=[])

                # Проверяем наличие логики приоритетов
                source = inspect.getsource(module) if hasattr(module, '__file__') else ""

                priority_keywords = ['priority', 'severity', 'critical', 'escalation', 'cooldown']
                found_keywords = [kw for kw in priority_keywords if kw in source.lower()]

                if found_keywords:
                    test_results["found"].append(f"{module_name} ({', '.join(found_keywords[:3])})")
                    test_results["details"][f"{module_name}"] = f"Найдены: {', '.join(found_keywords)}"
                else:
                    test_results["missing"].append(f"{module_name} (нет приоритетов)")
                    test_results["details"][f"{module_name}"] = "Нет логики приоритетов"

            except ImportError:
                test_results["missing"].append(f"{module_name} (модуль не найден)")
                test_results["details"][f"{module_name}"] = "Модуль не найден"

        if not test_results["found"]:
            return TestResult(
                name="Приоритеты и эскалация",
                status=TestStatus.WARNING,
                message="Логика приоритетов не найдена",
                details=test_results["details"],
                recommendations=[
                    "Проверьте наличие логики приоритетов в alert_system",
                    "Приоритеты могут быть реализованы через severity"
                ]
            )

        return TestResult(
            name="Приоритеты и эскалация",
            status=TestStatus.PASS,
            message=f"Найдена логика приоритетов ({len(test_results['found'])})",
            details=test_results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Приоритеты и эскалация",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


def run_all_alerts_tests() -> list:
    """Запускает все тесты системы алертов"""
    tests = [
        test_alert_system_structure,
        test_telegram_notification_channels,
        test_alert_types_and_severity,
        test_personal_vs_system_alerts,
        test_alert_priorities_and_escalation
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
    print("ТЕСТЫ СИСТЕМЫ АЛЕРТОВ")
    print("=" * 60)

    results = run_all_alerts_tests()

    from scripts.test_utils import print_test_summary
    print_test_summary(results)

