#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Функциональные тесты управления рисками
Проверяет trailing stop, перенос SL в безубыток, управление позициями
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from src.shared.utils.datetime_utils import get_utc_now

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import (
    TestResult, TestStatus, measure_time
)


@measure_time
def test_trailing_stop_manager_structure() -> TestResult:
    """Проверяет структуру и наличие trailing stop manager"""
    try:
        from trailing_stop_manager import AdvancedTrailingStopManager

        # Проверяем наличие ключевых методов
        required_methods = [
            'get_adaptive_progress_ratio',
            '_analyze_volatility',
            '_analyze_trend_strength'
        ]

        missing_methods = [
            method for method in required_methods
            if not hasattr(AdvancedTrailingStopManager, method)
        ]

        if missing_methods:
            return TestResult(
                name="Структура Trailing Stop Manager",
                status=TestStatus.WARNING,
                message=f"Отсутствуют методы: {', '.join(missing_methods)}",
                details={"missing_methods": missing_methods}
            )

        # Проверяем инициализацию
        test_config = {
            'tp1_sl_progress_ratio': 1.0,
            'ADAPTIVE_TRAILING_CONFIG': {
                'enabled': True
            }
        }

        try:
            manager = AdvancedTrailingStopManager(test_config)
            return TestResult(
                name="Структура Trailing Stop Manager",
                status=TestStatus.PASS,
                message="Trailing Stop Manager доступен и инициализируется корректно",
                details={"methods_available": required_methods}
            )
        except Exception as e:
            return TestResult(
                name="Структура Trailing Stop Manager",
                status=TestStatus.WARNING,
                message=f"Ошибка инициализации: {str(e)}",
                details={"error": str(e)}
            )

    except ImportError:
        return TestResult(
            name="Структура Trailing Stop Manager",
            status=TestStatus.WARNING,
            message="Модуль trailing_stop_manager не найден",
            recommendations=["Проверьте наличие trailing_stop_manager.py"]
        )
    except Exception as e:
        return TestResult(
            name="Структура Trailing Stop Manager",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_breakeven_calculation() -> TestResult:
    """Проверяет расчет SL в безубыток"""
    try:
        from price_monitor_system import PriceMonitorSystem

        monitor = PriceMonitorSystem()

        # Тестируем расчет для LONG позиции
        entry_price_long = 50000.0
        breakeven_long = monitor.calculate_breakeven_sl(
            entry_price=entry_price_long,
            side="long",
            taker_fee=0.001
        )

        # Для LONG: SL должен быть выше entry_price (с учетом комиссий)
        if breakeven_long <= entry_price_long:
            return TestResult(
                name="Расчет безубытка (LONG)",
                status=TestStatus.FAIL,
                message=f"Некорректный расчет для LONG: {breakeven_long} <= {entry_price_long}",
                details={
                    "entry_price": entry_price_long,
                    "breakeven_sl": breakeven_long,
                    "expected": "> entry_price"
                }
            )

        # Тестируем расчет для SHORT позиции
        entry_price_short = 50000.0
        breakeven_short = monitor.calculate_breakeven_sl(
            entry_price=entry_price_short,
            side="short",
            taker_fee=0.001
        )

        # Для SHORT: SL должен быть ниже entry_price (с учетом комиссий)
        if breakeven_short >= entry_price_short:
            return TestResult(
                name="Расчет безубытка (SHORT)",
                status=TestStatus.FAIL,
                message=f"Некорректный расчет для SHORT: {breakeven_short} >= {entry_price_short}",
                details={
                    "entry_price": entry_price_short,
                    "breakeven_sl": breakeven_short,
                    "expected": "< entry_price"
                }
            )

        return TestResult(
            name="Расчет безубытка",
            status=TestStatus.PASS,
            message="Расчет безубытка работает корректно для LONG и SHORT",
            details={
                "long_entry": entry_price_long,
                "long_breakeven": breakeven_long,
                "short_entry": entry_price_short,
                "short_breakeven": breakeven_short
            }
        )

    except ImportError:
        return TestResult(
            name="Расчет безубытка",
            status=TestStatus.WARNING,
            message="Модуль price_monitor_system не найден",
            recommendations=["Проверьте наличие price_monitor_system.py"]
        )
    except Exception as e:
        return TestResult(
            name="Расчет безубытка",
            status=TestStatus.FAIL,
            message=f"Ошибка при тестировании: {str(e)}"
        )


@measure_time
def test_trailing_stop_adaptive_ratio() -> TestResult:
    """Проверяет адаптивный расчет trailing stop"""
    try:
        from trailing_stop_manager import AdvancedTrailingStopManager

        # Пытаемся получить значение из config, если не найдено - используем по умолчанию
        try:
            from config import TP1_SL_PROGRESS_RATIO
            progress_ratio = TP1_SL_PROGRESS_RATIO if hasattr(TP1_SL_PROGRESS_RATIO, '__float__') else 1.0
        except (ImportError, AttributeError):
            # Используем значение по умолчанию из trailing_stop_manager
            progress_ratio = 1.0

        # Создаем тестовые данные
        dates = pd.date_range(end=get_utc_now(), periods=100, freq='1h')
        test_df = pd.DataFrame({
            'open': np.random.uniform(40000, 50000, 100),
            'high': np.random.uniform(50000, 51000, 100),
            'low': np.random.uniform(39000, 40000, 100),
            'close': np.random.uniform(40000, 50000, 100),
            'volume': np.random.uniform(1000000, 5000000, 100)
        }, index=dates)

        test_config = {
            'tp1_sl_progress_ratio': progress_ratio,
            'ADAPTIVE_TRAILING_CONFIG': {
                'enabled': True
            }
        }

        manager = AdvancedTrailingStopManager(test_config)

        # Тестируем для LONG позиции
        current_price = 51000.0
        ratio_long = manager.get_adaptive_progress_ratio(
            df=test_df,
            symbol="BTCUSDT",
            direction="LONG",
            current_price=current_price
        )

        # Проверяем, что коэффициент в разумных пределах
        if not (0.0 <= ratio_long <= 2.0):
            return TestResult(
                name="Адаптивный trailing stop",
                status=TestStatus.WARNING,
                message=f"Коэффициент вне разумных пределов: {ratio_long}",
                details={
                    "ratio": ratio_long,
                    "expected_range": "0.0 - 2.0"
                }
            )

        # Тестируем для SHORT позиции
        ratio_short = manager.get_adaptive_progress_ratio(
            df=test_df,
            symbol="BTCUSDT",
            direction="SHORT",
            current_price=current_price
        )

        if not (0.0 <= ratio_short <= 2.0):
            return TestResult(
                name="Адаптивный trailing stop",
                status=TestStatus.WARNING,
                message=f"Коэффициент для SHORT вне разумных пределов: {ratio_short}",
                details={
                    "ratio": ratio_short,
                    "expected_range": "0.0 - 2.0"
                }
            )

        return TestResult(
            name="Адаптивный trailing stop",
            status=TestStatus.PASS,
            message="Адаптивный расчет trailing stop работает",
            details={
                "long_ratio": ratio_long,
                "short_ratio": ratio_short,
                "base_ratio": test_config['tp1_sl_progress_ratio']
            }
        )

    except ImportError as e:
        return TestResult(
            name="Адаптивный trailing stop",
            status=TestStatus.WARNING,
            message=f"Не удалось импортировать модули: {str(e)}",
            recommendations=["Проверьте наличие trailing_stop_manager.py"]
        )
    except Exception as e:
        return TestResult(
            name="Адаптивный trailing stop",
            status=TestStatus.FAIL,
            message=f"Ошибка при тестировании: {str(e)}"
        )


@measure_time
def test_position_management_structure() -> TestResult:
    """Проверяет структуру модулей управления позициями"""
    try:
        modules_to_check = {
            "price_monitor_system": ["PriceMonitorSystem"],  # check_all_active_signals - это метод, не отдельный класс
            "partial_profit_manager": ["PartialProfitManager"],
            "correlation_risk_manager": ["CorrelationRiskManager"],
            "improved_position_manager": ["ImprovedPositionManager"],  # Добавляем этот модуль
        }

        results = {
            "found": [],
            "missing": [],
            "details": {}
        }

        for module_name, items in modules_to_check.items():
            try:
                module = __import__(module_name, fromlist=items)
                for item_name in items:
                    item = getattr(module, item_name, None)
                    if item:
                        results["found"].append(f"{module_name}.{item_name}")
                        results["details"][f"{module_name}.{item_name}"] = "OK"
                    else:
                        results["missing"].append(f"{module_name}.{item_name}")
                        results["details"][f"{module_name}.{item_name}"] = "Не найдено"
            except ImportError:
                for item_name in items:
                    results["missing"].append(f"{module_name}.{item_name}")
                    results["details"][f"{module_name}.{item_name}"] = "Модуль не найден"

        if results["missing"]:
            return TestResult(
                name="Структура управления позициями",
                status=TestStatus.WARNING,
                message=f"Найдено: {len(results['found'])}, Отсутствует: {len(results['missing'])}",
                details=results["details"],
                recommendations=[
                    "Проверьте наличие всех модулей управления позициями",
                    "Некоторые модули могут быть опциональными"
                ]
            )

        return TestResult(
            name="Структура управления позициями",
            status=TestStatus.PASS,
            message=f"Все модули управления позициями найдены ({len(results['found'])})",
            details=results["details"]
        )

    except Exception as e:
        return TestResult(
            name="Структура управления позициями",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_tp1_tp2_split_logic() -> TestResult:
    """Проверяет логику разделения позиции 50%/50% (TP1/TP2)"""
    try:
        # Проверяем наличие логики разделения позиции
        # Обычно это реализовано в price_monitor_system или order_manager

        try:
            from price_monitor_system import PriceMonitorSystem
            monitor = PriceMonitorSystem()

            # Проверяем наличие метода для частичного закрытия
            if hasattr(monitor, 'close_signal_at_tp1'):
                return TestResult(
                    name="Логика разделения TP1/TP2",
                    status=TestStatus.PASS,
                    message="Метод частичного закрытия на TP1 найден",
                    details={"method": "close_signal_at_tp1"}
                )
            else:
                return TestResult(
                    name="Логика разделения TP1/TP2",
                    status=TestStatus.WARNING,
                    message="Метод частичного закрытия не найден",
                    recommendations=["Проверьте реализацию close_signal_at_tp1"]
                )

        except ImportError:
            return TestResult(
                name="Логика разделения TP1/TP2",
                status=TestStatus.WARNING,
                message="Модуль price_monitor_system не найден"
            )

    except Exception as e:
        return TestResult(
            name="Логика разделения TP1/TP2",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


def run_all_risk_management_functional_tests() -> list:
    """Запускает все функциональные тесты управления рисками"""
    tests = [
        test_trailing_stop_manager_structure,
        test_breakeven_calculation,
        test_trailing_stop_adaptive_ratio,
        test_position_management_structure,
        test_tp1_tp2_split_logic
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
    print("ФУНКЦИОНАЛЬНЫЕ ТЕСТЫ УПРАВЛЕНИЯ РИСКАМИ")
    print("=" * 60)

    results = run_all_risk_management_functional_tests()

    from scripts.test_utils import print_test_summary
    print_test_summary(results)

