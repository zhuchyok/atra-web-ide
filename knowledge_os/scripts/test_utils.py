#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Общие утилиты для тестовых скриптов
"""

import os
import sys
import json
import time
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from enum import Enum

from src.shared.utils.datetime_utils import get_utc_now

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Статусы проверок"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    SKIP = "SKIP"


class TestResult:
    """Результат проверки"""
    
    def __init__(
        self,
        name: str,
        status: TestStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
        recommendations: Optional[List[str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        duration: float = 0.0
    ):
        self.name = name
        self.status = status
        self.message = message
        self.details = details or {}
        self.recommendations = recommendations or []
        self.metrics = metrics or {}
        self.duration = duration
        self.timestamp = get_utc_now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует результат в словарь"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "recommendations": self.recommendations,
            "metrics": self.metrics,
            "duration": self.duration,
            "timestamp": self.timestamp
        }
    
    def __str__(self) -> str:
        status_icon = {
            TestStatus.PASS: "✅",
            TestStatus.FAIL: "❌",
            TestStatus.WARNING: "⚠️",
            TestStatus.SKIP: "⏭️"
        }
        icon = status_icon.get(self.status, "❓")
        return f"{icon} {self.name}: {self.status.value} - {self.message}"


def get_db_connection(db_path: str = "trading.db") -> Optional[sqlite3.Connection]:
    """Получает соединение с БД"""
    try:
        if not os.path.exists(db_path):
            logger.warning(f"База данных {db_path} не найдена")
            return None
        
        conn = sqlite3.connect(db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        return None


def check_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Проверяет существование таблицы"""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Ошибка проверки таблицы {table_name}: {e}")
        return False


def get_table_structure(conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    """Получает структуру таблицы"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                "name": row[1],
                "type": row[2],
                "not_null": bool(row[3]),
                "default_value": row[4],
                "primary_key": bool(row[5])
            })
        return columns
    except sqlite3.Error as e:
        logger.error(f"Ошибка получения структуры таблицы {table_name}: {e}")
        return []


def get_table_row_count(conn: sqlite3.Connection, table_name: str) -> int:
    """Получает количество записей в таблице"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]
    except sqlite3.Error as e:
        logger.error(f"Ошибка подсчета записей в таблице {table_name}: {e}")
        return -1


def check_file_exists(file_path: str) -> bool:
    """Проверяет существование файла"""
    return os.path.exists(file_path)


def check_module_import(module_name: str) -> Tuple[bool, Optional[str]]:
    """Проверяет возможность импорта модуля"""
    try:
        __import__(module_name)
        return True, None
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Неожиданная ошибка: {str(e)}"


def check_class_exists(module_name: str, class_name: str) -> Tuple[bool, Optional[str]]:
    """Проверяет существование класса в модуле"""
    try:
        module = __import__(module_name, fromlist=[class_name])
        if hasattr(module, class_name):
            return True, None
        return False, f"Класс {class_name} не найден в модуле {module_name}"
    except ImportError as e:
        return False, str(e)


def check_function_exists(module_name: str, function_name: str) -> Tuple[bool, Optional[str]]:
    """Проверяет существование функции в модуле"""
    try:
        module = __import__(module_name, fromlist=[function_name])
        if hasattr(module, function_name):
            func = getattr(module, function_name)
            if callable(func):
                return True, None
            return False, f"{function_name} не является функцией"
        return False, f"Функция {function_name} не найдена в модуле {module_name}"
    except ImportError as e:
        return False, str(e)


def measure_time(func):
    """Декоратор для измерения времени выполнения"""
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        duration = time.perf_counter() - start_time
        if isinstance(result, TestResult):
            result.duration = duration
        return result
    return wrapper


def format_duration(seconds: float) -> str:
    """Форматирует длительность в читаемый формат"""
    if seconds < 0.001:
        return f"{seconds * 1000000:.2f} μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f} ms"
    else:
        return f"{seconds:.2f} s"


def format_bytes(bytes_count: int) -> str:
    """Форматирует размер в байтах"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} PB"


def get_file_size(file_path: str) -> int:
    """Получает размер файла в байтах"""
    try:
        return os.path.getsize(file_path)
    except OSError:
        return -1


def get_file_path(relative_path: str, project_root: Optional[Path] = None) -> str:
    """Получает абсолютный путь к файлу относительно корня проекта"""
    if project_root is None:
        # Определяем корень проекта (на 2 уровня выше scripts/)
        project_root = Path(__file__).parent.parent
    return str(project_root / relative_path)


def ensure_directory(path: str) -> bool:
    """Создает директорию, если она не существует"""
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except OSError as e:
        logger.error(f"Ошибка создания директории {path}: {e}")
        return False


def save_json_report(results: List[TestResult], output_path: str) -> bool:
    """Сохраняет отчет в формате JSON"""
    try:
        ensure_directory(os.path.dirname(output_path) if os.path.dirname(output_path) else ".")
        report = {
            "timestamp": get_utc_now().isoformat(),
            "total_tests": len(results),
            "passed": sum(1 for r in results if r.status == TestStatus.PASS),
            "failed": sum(1 for r in results if r.status == TestStatus.FAIL),
            "warnings": sum(1 for r in results if r.status == TestStatus.WARNING),
            "skipped": sum(1 for r in results if r.status == TestStatus.SKIP),
            "results": [r.to_dict() for r in results]
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения JSON отчета: {e}")
        return False


def print_test_summary(results: List[TestResult]):
    """Выводит сводку результатов тестов"""
    total = len(results)
    passed = sum(1 for r in results if r.status == TestStatus.PASS)
    failed = sum(1 for r in results if r.status == TestStatus.FAIL)
    warnings = sum(1 for r in results if r.status == TestStatus.WARNING)
    skipped = sum(1 for r in results if r.status == TestStatus.SKIP)
    
    print("\n" + "=" * 60)
    print("СВОДКА РЕЗУЛЬТАТОВ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"Всего проверок: {total}")
    print(f"✅ Успешно: {passed}")
    print(f"❌ Провалено: {failed}")
    print(f"⚠️  Предупреждений: {warnings}")
    print(f"⏭️  Пропущено: {skipped}")
    
    if failed > 0:
        print("\n❌ ПРОВАЛЕННЫЕ ПРОВЕРКИ:")
        for result in results:
            if result.status == TestStatus.FAIL:
                print(f"  - {result.name}: {result.message}")
                if result.recommendations:
                    for rec in result.recommendations:
                        print(f"    💡 {rec}")
    
    if warnings > 0:
        print("\n⚠️  ПРЕДУПРЕЖДЕНИЯ:")
        for result in results:
            if result.status == TestStatus.WARNING:
                print(f"  - {result.name}: {result.message}")
    
    print("=" * 60)


if __name__ == "__main__":
    # Тестирование утилит
    print("Тестирование утилит...")
    
    # Тест проверки файла
    test_file = "test_utils.py"
    exists = check_file_exists(test_file)
    print(f"Файл {test_file} существует: {exists}")
    
    # Тест импорта модуля
    success, error = check_module_import("os")
    print(f"Импорт модуля 'os': {success}, ошибка: {error}")
    
    print("Тестирование завершено")

