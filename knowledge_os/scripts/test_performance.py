#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка производительности
"""

import sys
import os
import time
import psutil
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import TestResult, TestStatus, measure_time, format_duration


@measure_time
def test_cpu_usage() -> TestResult:
    """Проверяет использование CPU"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Предупреждение при высоком использовании CPU
        status = TestStatus.PASS
        message = f"Использование CPU: {cpu_percent:.1f}%"
        
        if cpu_percent > 80:
            status = TestStatus.WARNING
            message += " (высокое использование)"
        elif cpu_percent > 95:
            status = TestStatus.FAIL
            message += " (критическое использование)"
        
        return TestResult(
            name="Использование CPU",
            status=status,
            message=message,
            details={
                "cpu_percent": cpu_percent,
                "cpu_count": cpu_count
            },
            metrics={"cpu_usage_percent": cpu_percent}
        )
    except ImportError:
        return TestResult(
            name="Использование CPU",
            status=TestStatus.SKIP,
            message="Библиотека psutil не установлена",
            recommendations=["Установите: pip install psutil"]
        )
    except Exception as e:
        return TestResult(
            name="Использование CPU",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке CPU: {str(e)}"
        )


@measure_time
def test_memory_usage() -> TestResult:
    """Проверяет использование памяти"""
    try:
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_gb = memory.available / (1024 ** 3)
        
        status = TestStatus.PASS
        message = f"Использование памяти: {memory_percent:.1f}%"
        
        if memory_percent > 85:
            status = TestStatus.WARNING
            message += " (высокое использование)"
        elif memory_percent > 95:
            status = TestStatus.FAIL
            message += " (критическое использование)"
        
        return TestResult(
            name="Использование памяти",
            status=status,
            message=message,
            details={
                "memory_percent": memory_percent,
                "memory_total_gb": memory.total / (1024 ** 3),
                "memory_available_gb": memory_available_gb,
                "memory_used_gb": memory.used / (1024 ** 3)
            },
            metrics={
                "memory_usage_percent": memory_percent,
                "memory_available_gb": memory_available_gb
            }
        )
    except ImportError:
        return TestResult(
            name="Использование памяти",
            status=TestStatus.SKIP,
            message="Библиотека psutil не установлена",
            recommendations=["Установите: pip install psutil"]
        )
    except Exception as e:
        return TestResult(
            name="Использование памяти",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке памяти: {str(e)}"
        )


@measure_time
def test_database_performance() -> TestResult:
    """Проверяет производительность БД"""
    try:
        from scripts.test_utils import get_db_connection
        from scripts.test_config import DATABASE_PATH
        
        conn = get_db_connection(DATABASE_PATH)
        if conn is None:
            return TestResult(
                name="Производительность БД",
                status=TestStatus.FAIL,
                message="Не удалось подключиться к БД"
            )
        
        try:
            cursor = conn.cursor()
            
            # Тест простого запроса
            start_time = time.perf_counter()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            simple_query_time = time.perf_counter() - start_time
            
            # Тест запроса к таблице (если есть)
            start_time = time.perf_counter()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 10")
            cursor.fetchall()
            table_query_time = time.perf_counter() - start_time
            
            conn.close()
            
            # Проверяем производительность
            status = TestStatus.PASS
            message = "Производительность БД в норме"
            
            if simple_query_time > 0.1:
                status = TestStatus.WARNING
                message = "Медленные запросы к БД"
            
            return TestResult(
                name="Производительность БД",
                status=status,
                message=message,
                details={
                    "simple_query_time": format_duration(simple_query_time),
                    "table_query_time": format_duration(table_query_time)
                },
                metrics={
                    "simple_query_ms": simple_query_time * 1000,
                    "table_query_ms": table_query_time * 1000
                }
            )
        except Exception as e:
            conn.close()
            return TestResult(
                name="Производительность БД",
                status=TestStatus.FAIL,
                message=f"Ошибка при тестировании: {str(e)}"
            )
    except Exception as e:
        return TestResult(
            name="Производительность БД",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


@measure_time
def test_disk_io() -> TestResult:
    """Проверяет использование диска"""
    try:
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_free_gb = disk.free / (1024 ** 3)
        
        status = TestStatus.PASS
        message = f"Использование диска: {disk_percent:.1f}%"
        
        if disk_percent > 85:
            status = TestStatus.WARNING
            message += " (мало свободного места)"
        elif disk_percent > 95:
            status = TestStatus.FAIL
            message += " (критически мало места)"
        
        return TestResult(
            name="Использование диска",
            status=status,
            message=message,
            details={
                "disk_percent": disk_percent,
                "disk_total_gb": disk.total / (1024 ** 3),
                "disk_free_gb": disk_free_gb,
                "disk_used_gb": disk.used / (1024 ** 3)
            },
            metrics={
                "disk_usage_percent": disk_percent,
                "disk_free_gb": disk_free_gb
            }
        )
    except ImportError:
        return TestResult(
            name="Использование диска",
            status=TestStatus.SKIP,
            message="Библиотека psutil не установлена"
        )
    except Exception as e:
        return TestResult(
            name="Использование диска",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке диска: {str(e)}"
        )


def run_all_performance_tests() -> list:
    """Запускает все тесты производительности"""
    tests = [
        test_cpu_usage,
        test_memory_usage,
        test_database_performance,
        test_disk_io
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
    print("ПРОВЕРКА ПРОИЗВОДИТЕЛЬНОСТИ")
    print("=" * 60)
    
    results = run_all_performance_tests()
    
    from scripts.test_utils import print_test_summary
    print_test_summary(results)

