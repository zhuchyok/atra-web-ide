#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка структуры базы данных
"""

import sys
import os
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import (
    TestResult, TestStatus, get_db_connection, check_table_exists,
    get_table_structure, get_table_row_count, measure_time
)
from scripts.test_config import REQUIRED_DB_TABLES, DATABASE_PATH


@measure_time
def test_database_connection() -> TestResult:
    """Проверяет подключение к базе данных"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Подключение к БД",
            status=TestStatus.FAIL,
            message=f"Не удалось подключиться к базе данных {DATABASE_PATH}",
            recommendations=[
                f"Убедитесь, что файл {DATABASE_PATH} существует",
                "Проверьте права доступа к файлу БД",
                "Запустите инициализацию БД: python database_initialization.py"
            ]
        )
    
    try:
        # Простой тест запроса
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        conn.close()
        
        return TestResult(
            name="Подключение к БД",
            status=TestStatus.PASS,
            message=f"Успешное подключение к {DATABASE_PATH}",
            metrics={"db_path": DATABASE_PATH}
        )
    except Exception as e:
        conn.close()
        return TestResult(
            name="Подключение к БД",
            status=TestStatus.FAIL,
            message=f"Ошибка при выполнении запроса: {str(e)}",
            recommendations=["Проверьте целостность базы данных"]
        )


@measure_time
def test_required_tables_exist() -> TestResult:
    """Проверяет наличие всех требуемых таблиц"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Проверка таблиц",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    missing_tables = []
    existing_tables = []
    
    try:
        for table_name in REQUIRED_DB_TABLES:
            if check_table_exists(conn, table_name):
                existing_tables.append(table_name)
            else:
                missing_tables.append(table_name)
        
        conn.close()
        
        if missing_tables:
            return TestResult(
                name="Проверка таблиц",
                status=TestStatus.FAIL,
                message=f"Отсутствуют таблицы: {', '.join(missing_tables)}",
                details={
                    "existing": existing_tables,
                    "missing": missing_tables,
                    "total_required": len(REQUIRED_DB_TABLES),
                    "total_existing": len(existing_tables)
                },
                recommendations=[
                    "Запустите инициализацию БД: python database_initialization.py",
                    "Проверьте миграции БД",
                    f"Убедитесь, что все таблицы созданы: {', '.join(missing_tables)}"
                ]
            )
        
        return TestResult(
            name="Проверка таблиц",
            status=TestStatus.PASS,
            message=f"Все {len(REQUIRED_DB_TABLES)} требуемых таблиц существуют",
            details={
                "tables": existing_tables,
                "total": len(existing_tables)
            }
        )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Проверка таблиц",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке таблиц: {str(e)}"
        )


@measure_time
def test_table_structures() -> TestResult:
    """Проверяет структуру таблиц"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Структура таблиц",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    table_structures = {}
    errors = []
    
    try:
        for table_name in REQUIRED_DB_TABLES:
            if not check_table_exists(conn, table_name):
                errors.append(f"Таблица {table_name} не существует")
                continue
            
            structure = get_table_structure(conn, table_name)
            if structure:
                table_structures[table_name] = structure
            else:
                errors.append(f"Не удалось получить структуру таблицы {table_name}")
        
        conn.close()
        
        if errors:
            return TestResult(
                name="Структура таблиц",
                status=TestStatus.WARNING,
                message=f"Проблемы со структурой: {len(errors)} ошибок",
                details={
                    "errors": errors,
                    "tables_checked": len(table_structures)
                },
                recommendations=["Проверьте логи для деталей"]
            )
        
        return TestResult(
            name="Структура таблиц",
            status=TestStatus.PASS,
            message=f"Структура всех {len(table_structures)} таблиц корректна",
            details={
                "tables_checked": len(table_structures),
                "sample_structure": table_structures.get(REQUIRED_DB_TABLES[0], {}) if REQUIRED_DB_TABLES else {}
            }
        )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Структура таблиц",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке структуры: {str(e)}"
        )


@measure_time
def test_table_data_integrity() -> TestResult:
    """Проверяет целостность данных в таблицах"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Целостность данных",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    table_counts = {}
    empty_tables = []
    
    try:
        for table_name in REQUIRED_DB_TABLES:
            if not check_table_exists(conn, table_name):
                continue
            
            count = get_table_row_count(conn, table_name)
            table_counts[table_name] = count
            
            if count == 0:
                empty_tables.append(table_name)
        
        conn.close()
        
        # Проверка целостности через PRAGMA integrity_check
        conn = get_db_connection(DATABASE_PATH)
        if conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()
            conn.close()
            
            if integrity_result and integrity_result[0] != "ok":
                return TestResult(
                    name="Целостность данных",
                    status=TestStatus.FAIL,
                    message=f"Обнаружены проблемы целостности: {integrity_result[0]}",
                    details={
                        "table_counts": table_counts,
                        "integrity_check": integrity_result[0]
                    },
                    recommendations=[
                        "Выполните резервное копирование БД",
                        "Проверьте логи на наличие ошибок",
                        "Рассмотрите возможность восстановления из бэкапа"
                    ]
                )
        
        # Информация о пустых таблицах (не критично, но нормально)
        if empty_tables:
            # Разделяем на критичные и некритичные пустые таблицы
            critical_empty = [t for t in empty_tables if t in ["signals_log", "accepted_signals", "active_positions"]]
            non_critical_empty = [t for t in empty_tables if t not in critical_empty]
            
            if critical_empty:
                return TestResult(
                    name="Целостность данных",
                    status=TestStatus.WARNING,
                    message=f"Критичные таблицы пусты: {len(critical_empty)}",
                    details={
                        "table_counts": table_counts,
                        "critical_empty": critical_empty,
                        "non_critical_empty": non_critical_empty
                    },
                    recommendations=[
                        "Критичные таблицы должны содержать данные",
                        "Проверьте работу системы генерации сигналов"
                    ]
                )
            else:
                # Только некритичные таблицы пусты - это нормально
                return TestResult(
                    name="Целостность данных",
                    status=TestStatus.PASS,
                    message=f"Целостность данных проверена. Некоторые таблицы пусты (нормально для новой установки)",
                    details={
                        "table_counts": table_counts,
                        "empty_tables": empty_tables,
                        "note": "Пустые таблицы заполнятся при работе системы"
                    }
                )
        
        return TestResult(
            name="Целостность данных",
            status=TestStatus.PASS,
            message="Целостность данных проверена успешно",
            details={
                "table_counts": table_counts,
                "total_tables": len(table_counts)
            },
            metrics={
                "total_records": sum(table_counts.values()),
                "tables_with_data": len([t for t, c in table_counts.items() if c > 0])
            }
        )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Целостность данных",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке целостности: {str(e)}"
        )


@measure_time
def test_critical_tables_have_data() -> TestResult:
    """Проверяет наличие данных в критических таблицах"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Данные в критических таблицах",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    # Критические таблицы, которые должны содержать данные для работы системы
    critical_tables = [
        "system_settings",  # Настройки системы
        "user_settings"  # Настройки пользователей (может быть пусто)
    ]
    
    table_status = {}
    
    try:
        for table_name in critical_tables:
            if not check_table_exists(conn, table_name):
                table_status[table_name] = "missing"
                continue
            
            count = get_table_row_count(conn, table_name)
            table_status[table_name] = {
                "exists": True,
                "row_count": count,
                "has_data": count > 0
            }
        
        conn.close()
        
        missing_tables = [t for t, s in table_status.items() if s == "missing"]
        empty_tables = [
            t for t, s in table_status.items()
            if isinstance(s, dict) and s.get("exists") and not s.get("has_data")
        ]
        
        if missing_tables:
            return TestResult(
                name="Данные в критических таблицах",
                status=TestStatus.FAIL,
                message=f"Отсутствуют критические таблицы: {', '.join(missing_tables)}",
                details={"table_status": table_status},
                recommendations=["Запустите инициализацию БД"]
            )
        
        if empty_tables:
            return TestResult(
                name="Данные в критических таблицах",
                status=TestStatus.WARNING,
                message=f"Критические таблицы пусты: {', '.join(empty_tables)}",
                details={"table_status": table_status},
                recommendations=[
                    "Проверьте, была ли выполнена инициализация БД",
                    "Некоторые таблицы могут быть пустыми при первом запуске"
                ]
            )
        
        return TestResult(
            name="Данные в критических таблицах",
            status=TestStatus.PASS,
            message="Критические таблицы содержат данные",
            details={"table_status": table_status}
        )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Данные в критических таблицах",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


def run_all_db_tests() -> list:
    """Запускает все тесты БД"""
    tests = [
        test_database_connection,
        test_required_tables_exist,
        test_table_structures,
        test_table_data_integrity,
        test_critical_tables_have_data
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
    print("ПРОВЕРКА СТРУКТУРЫ БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    results = run_all_db_tests()
    
    from scripts.test_utils import print_test_summary
    print_test_summary(results)

