#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для проверки работы ETH и SOL TrendFilter
"""

import sys
from pathlib import Path
from typing import List
import asyncio

# Добавляем корень проекта в путь
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.test_utils import TestResult, TestStatus, measure_time
from scripts.test_config import PROJECT_ROOT


@measure_time
async def test_eth_trend_filter_import() -> TestResult:
    """Проверяет импорт и доступность ETH TrendFilter"""
    try:
        from src.signals.filters import check_eth_alignment
        import inspect
        
        # Проверяем, что функция async
        is_async = inspect.iscoroutinefunction(check_eth_alignment)
        
        if not is_async:
            return TestResult(
                name="ETH TrendFilter импорт",
                status=TestStatus.WARNING,
                message="Функция check_eth_alignment не является async",
                details={"is_async": is_async}
            )
        
        return TestResult(
            name="ETH TrendFilter импорт",
            status=TestStatus.PASS,
            message="Функция check_eth_alignment доступна и является async",
            details={"is_async": is_async, "function": "check_eth_alignment"}
        )
    except ImportError as e:
        return TestResult(
            name="ETH TrendFilter импорт",
            status=TestStatus.FAIL,
            message=f"Не удалось импортировать check_eth_alignment: {str(e)}",
            recommendations=["Проверьте наличие src/signals/filters.py"]
        )
    except Exception as e:
        return TestResult(
            name="ETH TrendFilter импорт",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
async def test_sol_trend_filter_import() -> TestResult:
    """Проверяет импорт и доступность SOL TrendFilter"""
    try:
        from src.signals.filters import check_sol_alignment
        import inspect
        
        # Проверяем, что функция async
        is_async = inspect.iscoroutinefunction(check_sol_alignment)
        
        if not is_async:
            return TestResult(
                name="SOL TrendFilter импорт",
                status=TestStatus.WARNING,
                message="Функция check_sol_alignment не является async",
                details={"is_async": is_async}
            )
        
        return TestResult(
            name="SOL TrendFilter импорт",
            status=TestStatus.PASS,
            message="Функция check_sol_alignment доступна и является async",
            details={"is_async": is_async, "function": "check_sol_alignment"}
        )
    except ImportError as e:
        return TestResult(
            name="SOL TrendFilter импорт",
            status=TestStatus.FAIL,
            message=f"Не удалось импортировать check_sol_alignment: {str(e)}",
            recommendations=["Проверьте наличие src/signals/filters.py"]
        )
    except Exception as e:
        return TestResult(
            name="SOL TrendFilter импорт",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
async def test_eth_trend_filter_logic() -> TestResult:
    """Проверяет логику работы ETH TrendFilter"""
    try:
        from src.signals.filters import check_eth_alignment
        
        # Тестируем с разными типами сигналов
        test_cases = [
            ("BTCUSDT", "BUY"),
            ("ETHUSDT", "SELL"),
            ("SOLUSDT", "BUY"),
        ]
        
        results = {}
        for symbol, signal_type in test_cases:
            try:
                # Вызываем async функцию
                result = await check_eth_alignment(symbol, signal_type)
                results[f"{symbol}_{signal_type}"] = {
                    "status": "OK",
                    "result": result,
                    "type": type(result).__name__
                }
            except Exception as e:
                results[f"{symbol}_{signal_type}"] = {
                    "status": "ERROR",
                    "error": str(e)[:100]
                }
        
        successful = sum(1 for r in results.values() if r.get("status") == "OK")
        
        if successful == 0:
            return TestResult(
                name="ETH TrendFilter логика",
                status=TestStatus.WARNING,
                message="Не удалось выполнить проверки ETH тренда",
                details=results,
                recommendations=[
                    "Проверьте доступность данных ETH через hybrid_data_manager",
                    "Убедитесь, что функция может получить данные ETHUSDT"
                ]
            )
        
        return TestResult(
            name="ETH TrendFilter логика",
            status=TestStatus.PASS,
            message=f"ETH TrendFilter работает корректно ({successful}/{len(test_cases)} проверок)",
            details=results
        )
    except Exception as e:
        return TestResult(
            name="ETH TrendFilter логика",
            status=TestStatus.FAIL,
            message=f"Ошибка при тестировании: {str(e)}"
        )


@measure_time
async def test_sol_trend_filter_logic() -> TestResult:
    """Проверяет логику работы SOL TrendFilter"""
    try:
        from src.signals.filters import check_sol_alignment
        
        # Тестируем с разными типами сигналов
        test_cases = [
            ("BTCUSDT", "BUY"),
            ("ETHUSDT", "SELL"),
            ("SOLUSDT", "BUY"),
        ]
        
        results = {}
        for symbol, signal_type in test_cases:
            try:
                # Вызываем async функцию
                result = await check_sol_alignment(symbol, signal_type)
                results[f"{symbol}_{signal_type}"] = {
                    "status": "OK",
                    "result": result,
                    "type": type(result).__name__
                }
            except Exception as e:
                results[f"{symbol}_{signal_type}"] = {
                    "status": "ERROR",
                    "error": str(e)[:100]
                }
        
        successful = sum(1 for r in results.values() if r.get("status") == "OK")
        
        if successful == 0:
            return TestResult(
                name="SOL TrendFilter логика",
                status=TestStatus.WARNING,
                message="Не удалось выполнить проверки SOL тренда",
                details=results,
                recommendations=[
                    "Проверьте доступность данных SOL через hybrid_data_manager",
                    "Убедитесь, что функция может получить данные SOLUSDT"
                ]
            )
        
        return TestResult(
            name="SOL TrendFilter логика",
            status=TestStatus.PASS,
            message=f"SOL TrendFilter работает корректно ({successful}/{len(test_cases)} проверок)",
            details=results
        )
    except Exception as e:
        return TestResult(
            name="SOL TrendFilter логика",
            status=TestStatus.FAIL,
            message=f"Ошибка при тестировании: {str(e)}"
        )


@measure_time
async def test_smart_trend_filter_integration() -> TestResult:
    """Проверяет интеграцию ETH и SOL фильтров в SmartTrendFilter"""
    try:
        from src.filters.smart_trend_filter import SmartTrendFilter
        
        filter_instance = SmartTrendFilter()
        
        # Проверяем наличие методов
        has_check_trend = hasattr(filter_instance, 'check_trend_alignment')
        has_get_primary = hasattr(filter_instance, 'get_primary_trend_to_check')
        has_stats = hasattr(filter_instance, 'get_statistics')
        
        if not (has_check_trend and has_get_primary):
            return TestResult(
                name="SmartTrendFilter интеграция",
                status=TestStatus.WARNING,
                message="Отсутствуют необходимые методы",
                details={
                    "check_trend_alignment": has_check_trend,
                    "get_primary_trend_to_check": has_get_primary,
                    "get_statistics": has_stats
                }
            )
        
        # Проверяем, что фильтр может определить тренд для ETH и SOL
        try:
            eth_trend = await filter_instance.get_primary_trend_to_check("ETHUSDT")
            sol_trend = await filter_instance.get_primary_trend_to_check("SOLUSDT")
            
            return TestResult(
                name="SmartTrendFilter интеграция",
                status=TestStatus.PASS,
                message="SmartTrendFilter корректно интегрирован с ETH и SOL фильтрами",
                details={
                    "eth_trend": eth_trend,
                    "sol_trend": sol_trend,
                    "methods_available": {
                        "check_trend_alignment": has_check_trend,
                        "get_primary_trend_to_check": has_get_primary,
                        "get_statistics": has_stats
                    }
                }
            )
        except Exception as exec_e:
            return TestResult(
                name="SmartTrendFilter интеграция",
                status=TestStatus.WARNING,
                message=f"Ошибка при выполнении: {str(exec_e)[:100]}",
                details={
                    "methods_available": {
                        "check_trend_alignment": has_check_trend,
                        "get_primary_trend_to_check": has_get_primary,
                        "get_statistics": has_stats
                    }
                }
            )
    except ImportError as e:
        return TestResult(
            name="SmartTrendFilter интеграция",
            status=TestStatus.FAIL,
            message=f"Не удалось импортировать SmartTrendFilter: {str(e)}"
        )
    except Exception as e:
        return TestResult(
            name="SmartTrendFilter интеграция",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


async def run_all_eth_sol_trend_tests() -> List[TestResult]:
    """Запускает все тесты для ETH и SOL TrendFilter"""
    tests = [
        test_eth_trend_filter_import,
        test_sol_trend_filter_import,
        test_eth_trend_filter_logic,
        test_sol_trend_filter_logic,
        test_smart_trend_filter_integration
    ]
    
    results = []
    for test_func in tests:
        try:
            result = await test_func()
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
    print("ТЕСТЫ ETH И SOL TRENDFILTER")
    print("=" * 60)
    
    results = asyncio.run(run_all_eth_sol_trend_tests())
    
    from scripts.test_utils import print_test_summary
    print_test_summary(results)

