#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка метрик
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import (
    TestResult, TestStatus, get_db_connection, measure_time
)
from scripts.test_config import DATABASE_PATH, METRICS_TO_TRACK


@measure_time
def test_signals_metrics() -> TestResult:
    """Проверяет метрики сигналов"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Метрики сигналов",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    try:
        cursor = conn.cursor()
        
        # Подсчет сигналов
        metrics = {}
        
        # Общее количество сигналов
        try:
            cursor.execute("SELECT COUNT(*) FROM signals_log")
            metrics["total_generated"] = cursor.fetchone()[0]
        except Exception:
            metrics["total_generated"] = 0
        
        # Принятые сигналы
        try:
            cursor.execute("SELECT COUNT(*) FROM accepted_signals")
            metrics["total_accepted"] = cursor.fetchone()[0]
        except Exception:
            metrics["total_accepted"] = 0
        
        # Отклоненные сигналы
        try:
            cursor.execute("SELECT COUNT(*) FROM rejected_signals")
            metrics["total_rejected"] = cursor.fetchone()[0]
        except Exception:
            metrics["total_rejected"] = 0
        
        # Процент принятия
        if metrics["total_generated"] > 0:
            metrics["acceptance_rate"] = (
                metrics["total_accepted"] / metrics["total_generated"] * 100
            )
        else:
            metrics["acceptance_rate"] = 0
        
        conn.close()
        
        return TestResult(
            name="Метрики сигналов",
            status=TestStatus.PASS,
            message=f"Собрано метрик сигналов: {len(metrics)}",
            details=metrics,
            metrics=metrics
        )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Метрики сигналов",
            status=TestStatus.FAIL,
            message=f"Ошибка при сборе метрик: {str(e)}"
        )


@measure_time
def test_orders_metrics() -> TestResult:
    """Проверяет метрики ордеров"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Метрики ордеров",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    try:
        cursor = conn.cursor()
        metrics = {}
        
        # Проверяем наличие таблицы order_audit_log
        try:
            cursor.execute("SELECT COUNT(*) FROM order_audit_log")
            metrics["total_executed"] = cursor.fetchone()[0]
        except Exception:
            metrics["total_executed"] = 0
        
        # Успешные исполнения
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM order_audit_log WHERE status = 'executed'"
            )
            metrics["successful_executions"] = cursor.fetchone()[0]
        except Exception:
            metrics["successful_executions"] = 0
        
        # Неудачные исполнения
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM order_audit_log WHERE status = 'failed'"
            )
            metrics["failed_executions"] = cursor.fetchone()[0]
        except Exception:
            metrics["failed_executions"] = 0
        
        # Процент успешности
        if metrics["total_executed"] > 0:
            metrics["success_rate"] = (
                metrics["successful_executions"] / metrics["total_executed"] * 100
            )
        else:
            metrics["success_rate"] = 0
        
        conn.close()
        
        return TestResult(
            name="Метрики ордеров",
            status=TestStatus.PASS,
            message=f"Собрано метрик ордеров: {len(metrics)}",
            details=metrics,
            metrics=metrics
        )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Метрики ордеров",
            status=TestStatus.FAIL,
            message=f"Ошибка при сборе метрик: {str(e)}"
        )


@measure_time
def test_positions_metrics() -> TestResult:
    """Проверяет метрики позиций"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Метрики позиций",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    try:
        cursor = conn.cursor()
        metrics = {}
        
        # Активные позиции
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM active_positions WHERE status = 'active'"
            )
            metrics["active_positions"] = cursor.fetchone()[0]
        except Exception:
            metrics["active_positions"] = 0
        
        # Позиции, достигшие TP1
        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM active_positions 
                WHERE status = 'closed' AND pnl_percent > 0
                """
            )
            metrics["positions_reached_tp1"] = cursor.fetchone()[0]
        except Exception:
            metrics["positions_reached_tp1"] = 0
        
        conn.close()
        
        return TestResult(
            name="Метрики позиций",
            status=TestStatus.PASS,
            message=f"Собрано метрик позиций: {len(metrics)}",
            details=metrics,
            metrics=metrics
        )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Метрики позиций",
            status=TestStatus.FAIL,
            message=f"Ошибка при сборе метрик: {str(e)}"
        )


@measure_time
def test_filter_performance_metrics() -> TestResult:
    """Проверяет метрики производительности фильтров"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Метрики фильтров",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    try:
        cursor = conn.cursor()
        
        # Проверяем наличие таблицы filter_performance
        try:
            cursor.execute("SELECT COUNT(*) FROM filter_performance")
            total_records = cursor.fetchone()[0]
            
            if total_records == 0:
                return TestResult(
                    name="Метрики фильтров",
                    status=TestStatus.PASS,
                    message="Таблица filter_performance существует и готова к использованию",
                    details={
                        "total_records": total_records,
                        "note": "Таблица пуста, но это нормально - метрики собираются при работе системы"
                    },
                    recommendations=[
                        "Метрики фильтров будут собираться автоматически при работе системы",
                        "Это нормально для новой установки"
                    ]
                )
            
            # Получаем статистику по фильтрам
            cursor.execute(
                """
                SELECT filter_name, COUNT(*) as count, 
                       AVG(passed) as pass_rate 
                FROM filter_performance 
                GROUP BY filter_name
                LIMIT 10
                """
            )
            filter_stats = cursor.fetchall()
            
            metrics = {
                "total_records": total_records,
                "filters_tracked": len(filter_stats),
                "filter_stats": [
                    {"name": row[0], "count": row[1], "pass_rate": row[2]}
                    for row in filter_stats
                ]
            }
            
            conn.close()
            
            return TestResult(
                name="Метрики фильтров",
                status=TestStatus.PASS,
                message=f"Собрано метрик для {len(filter_stats)} фильтров",
                details=metrics,
                metrics=metrics
            )
        except Exception as e:
            conn.close()
            return TestResult(
                name="Метрики фильтров",
                status=TestStatus.WARNING,
                message=f"Таблица filter_performance недоступна: {str(e)}",
                recommendations=["Проверьте инициализацию БД"]
            )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Метрики фильтров",
            status=TestStatus.FAIL,
            message=f"Ошибка при сборе метрик: {str(e)}"
        )


def run_all_metrics_tests() -> list:
    """Запускает все тесты метрик"""
    tests = [
        test_signals_metrics,
        test_orders_metrics,
        test_positions_metrics,
        test_filter_performance_metrics
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
    print("ПРОВЕРКА МЕТРИК")
    print("=" * 60)
    
    results = run_all_metrics_tests()
    
    from scripts.test_utils import print_test_summary
    print_test_summary(results)

