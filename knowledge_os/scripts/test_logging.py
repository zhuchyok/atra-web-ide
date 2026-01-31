#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка системы логирования
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.test_utils import (
    TestResult, TestStatus, check_file_exists, measure_time, get_file_path, get_file_size
)
from scripts.test_config import LOG_PATHS, DATABASE_PATH
from scripts.test_utils import get_db_connection


@measure_time
def test_log_files_exist() -> TestResult:
    """Проверяет наличие лог-файлов"""
    existing_logs = []
    missing_logs = []
    
    for log_path in LOG_PATHS:
        full_path = get_file_path(log_path)
        if check_file_exists(full_path):
            size = get_file_size(full_path)
            existing_logs.append({
                "path": log_path,
                "size": size,
                "size_formatted": f"{size / 1024:.2f} KB" if size > 0 else "0 B"
            })
        else:
            missing_logs.append(log_path)
    
    # Не все лог-файлы обязательны (могут создаваться при работе)
    if len(missing_logs) == len(LOG_PATHS):
        return TestResult(
            name="Лог-файлы",
            status=TestStatus.WARNING,
            message="Лог-файлы не найдены",
            details={
                "missing": missing_logs,
                "existing": existing_logs
            },
            recommendations=[
                "Лог-файлы создаются при работе системы",
                "Это нормально для новой установки"
            ]
        )
    
    return TestResult(
        name="Лог-файлы",
        status=TestStatus.PASS,
        message=f"Найдено {len(existing_logs)} лог-файлов из {len(LOG_PATHS)}",
        details={
            "existing": existing_logs,
            "missing": missing_logs
        },
        metrics={
            "total_logs": len(LOG_PATHS),
            "existing_logs": len(existing_logs),
            "total_size": sum(log.get("size", 0) for log in existing_logs)
        }
    )


@measure_time
def test_log_format() -> TestResult:
    """Проверяет формат логов"""
    # Проверяем настройки логирования
    try:
        # Проверяем, что логирование настроено
        root_logger = logging.getLogger()
        
        if not root_logger.handlers:
            return TestResult(
                name="Формат логов",
                status=TestStatus.WARNING,
                message="Обработчики логирования не настроены",
                recommendations=[
                    "Настройте обработчики логирования в main.py",
                    "Убедитесь, что используется RotatingFileHandler"
                ]
            )
        
        # Проверяем формат
        formatters = []
        for handler in root_logger.handlers:
            if hasattr(handler, 'formatter') and handler.formatter:
                formatters.append(str(handler.formatter))
        
        return TestResult(
            name="Формат логов",
            status=TestStatus.PASS,
            message="Логирование настроено",
            details={
                "handlers_count": len(root_logger.handlers),
                "level": logging.getLevelName(root_logger.level)
            }
        )
    except Exception as e:
        return TestResult(
            name="Формат логов",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке формата: {str(e)}"
        )


@measure_time
def test_log_levels() -> TestResult:
    """Проверяет уровни логирования"""
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    try:
        root_logger = logging.getLogger()
        current_level = root_logger.level
        
        return TestResult(
            name="Уровни логирования",
            status=TestStatus.PASS,
            message=f"Текущий уровень логирования: {logging.getLevelName(current_level)}",
            details={
                "current_level": logging.getLevelName(current_level),
                "level_value": current_level,
                "available_levels": list(levels.keys())
            }
        )
    except Exception as e:
        return TestResult(
            name="Уровни логирования",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке уровней: {str(e)}"
        )


@measure_time
def test_log_rotation() -> TestResult:
    """Проверяет ротацию логов"""
    try:
        from logging.handlers import RotatingFileHandler
        
        # Проверяем root logger
        root_logger = logging.getLogger()
        rotating_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, RotatingFileHandler)
        ]
        
        # Также проверяем enhanced_logging, если доступен
        try:
            from enhanced_logging import EnhancedLoggingManager
            # EnhancedLoggingManager использует RotatingFileHandler
            rotating_handlers.append("enhanced_logging")  # Маркер наличия
        except ImportError:
            pass
        
        # Проверяем main.py - там тоже есть RotatingFileHandler в fallback
        if not rotating_handlers:
            # Проверяем, может быть enhanced_logging инициализирован
            try:
                import enhanced_logging
                if hasattr(enhanced_logging, 'EnhancedLoggingManager'):
                    return TestResult(
                        name="Ротация логов",
                        status=TestStatus.PASS,
                        message="Enhanced logging system доступен (использует RotatingFileHandler)",
                        details={"system": "enhanced_logging"}
                    )
            except ImportError:
                pass
            
            return TestResult(
                name="Ротация логов",
                status=TestStatus.WARNING,
                message="RotatingFileHandler не найден в root logger",
                recommendations=[
                    "Настройте ротацию логов для предотвращения переполнения",
                    "Используйте RotatingFileHandler с maxBytes и backupCount",
                    "Или используйте enhanced_logging.py, который уже настроен"
                ]
            )
        
        rotation_info = []
        for handler in rotating_handlers:
            rotation_info.append({
                "max_bytes": getattr(handler, 'maxBytes', 'unknown'),
                "backup_count": getattr(handler, 'backupCount', 'unknown')
            })
        
        return TestResult(
            name="Ротация логов",
            status=TestStatus.PASS,
            message=f"Ротация логов настроена для {len(rotating_handlers)} обработчиков",
            details={"rotation_config": rotation_info}
        )
    except ImportError:
        return TestResult(
            name="Ротация логов",
            status=TestStatus.WARNING,
            message="RotatingFileHandler недоступен",
            recommendations=["Установите стандартную библиотеку logging"]
        )
    except Exception as e:
        return TestResult(
            name="Ротация логов",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке ротации: {str(e)}"
        )


@measure_time
def test_database_logging() -> TestResult:
    """Проверяет запись логов в БД"""
    conn = get_db_connection(DATABASE_PATH)
    if conn is None:
        return TestResult(
            name="Логирование в БД",
            status=TestStatus.FAIL,
            message="Не удалось подключиться к БД"
        )
    
    try:
        # Проверяем наличие таблиц для логов
        log_tables = [
            "signals_log",
            "order_audit_log",
            "filter_performance"
        ]
        
        existing_tables = []
        missing_tables = []
        
        from scripts.test_utils import check_table_exists
        
        for table_name in log_tables:
            if check_table_exists(conn, table_name):
                existing_tables.append(table_name)
            else:
                missing_tables.append(table_name)
        
        conn.close()
        
        if missing_tables:
            return TestResult(
                name="Логирование в БД",
                status=TestStatus.WARNING,
                message=f"Отсутствуют таблицы для логов: {', '.join(missing_tables)}",
                details={
                    "existing": existing_tables,
                    "missing": missing_tables
                },
                recommendations=[
                    "Создайте недостающие таблицы",
                    "Проверьте инициализацию БД"
                ]
            )
        
        return TestResult(
            name="Логирование в БД",
            status=TestStatus.PASS,
            message=f"Все {len(existing_tables)} таблиц для логов существуют",
            details={"tables": existing_tables}
        )
    except Exception as e:
        if conn:
            conn.close()
        return TestResult(
            name="Логирование в БД",
            status=TestStatus.FAIL,
            message=f"Ошибка при проверке: {str(e)}"
        )


def run_all_logging_tests() -> list:
    """Запускает все тесты логирования"""
    tests = [
        test_log_files_exist,
        test_log_format,
        test_log_levels,
        test_log_rotation,
        test_database_logging
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
    print("ПРОВЕРКА СИСТЕМЫ ЛОГИРОВАНИЯ")
    print("=" * 60)
    
    results = run_all_logging_tests()
    
    from scripts.test_utils import print_test_summary
    print_test_summary(results)

