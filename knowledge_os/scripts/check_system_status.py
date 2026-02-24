#!/usr/bin/env python3
"""
Проверка статуса всех систем ATRA
"""

import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.shared.utils.datetime_utils import get_utc_now

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_processes() -> Dict[str, Any]:
    """Проверка запущенных процессов"""
    result = {"status": "unknown", "count": 0, "pids": [], "details": []}

    try:
        output = subprocess.check_output(
            ["pgrep", "-f", "python.*main.py"], stderr=subprocess.DEVNULL, text=True
        )
        pids = [int(pid.strip()) for pid in output.strip().split("\n") if pid.strip()]
        result["count"] = len(pids)
        result["pids"] = pids

        if len(pids) == 1:
            result["status"] = "ok"
            result["details"].append(f"✅ Найден 1 процесс (PID: {pids[0]})")
        elif len(pids) > 1:
            result["status"] = "warning"
            result["details"].append(f"⚠️ Найдено {len(pids)} процессов: {pids}")
        else:
            result["status"] = "error"
            result["details"].append("❌ Процесс main.py не найден")

    except subprocess.CalledProcessError:
        result["status"] = "error"
        result["details"].append("❌ Процесс main.py не найден")
    except Exception as e:
        result["status"] = "error"
        result["details"].append(f"❌ Ошибка проверки процессов: {e}")

    return result


def check_database() -> Dict[str, Any]:
    """Проверка базы данных"""
    result = {"status": "unknown", "details": []}

    db_paths = ["trading.db"]  # acceptance_signals.db консолидирована в trading.db

    for db_path in db_paths:
        if not os.path.exists(db_path):
            result["details"].append(f"⚠️ База данных {db_path} не найдена")
            continue

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            # Проверяем доступность
            cursor.execute("SELECT 1")
            cursor.fetchone()

            # Проверяем основные таблицы
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            conn.close()

            result["status"] = "ok"
            result["details"].append(f"✅ {db_path}: доступна ({len(tables)} таблиц)")

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                result["status"] = "warning"
                result["details"].append(f"⚠️ {db_path}: заблокирована")
            else:
                result["status"] = "error"
                result["details"].append(f"❌ {db_path}: ошибка - {e}")
        except Exception as e:
            result["status"] = "error"
            result["details"].append(f"❌ {db_path}: ошибка - {e}")

    return result


def check_logs() -> Dict[str, Any]:
    """Проверка последних логов на ошибки"""
    result = {"status": "unknown", "error_count": 0, "warnings": [], "errors": []}

    log_files = ["logs/main.log", "logs/system.log", "logs/error.log"]

    for log_file in log_files:
        if not os.path.exists(log_file):
            continue

        try:
            with open(log_file, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                # Берем последние 100 строк
                recent_lines = lines[-100:] if len(lines) > 100 else lines

                for line in recent_lines:
                    line_lower = line.lower()
                    if "error" in line_lower or "exception" in line_lower:
                        result["error_count"] += 1
                        if len(result["errors"]) < 5:
                            result["errors"].append(line.strip()[:200])
                    elif "warning" in line_lower:
                        if len(result["warnings"]) < 5:
                            result["warnings"].append(line.strip()[:200])

        except Exception as e:
            result["warnings"].append(f"Не удалось прочитать {log_file}: {e}")

    if result["error_count"] == 0:
        result["status"] = "ok"
    elif result["error_count"] < 5:
        result["status"] = "warning"
    else:
        result["status"] = "error"

    return result


def check_imports() -> Dict[str, Any]:
    """Проверка основных импортов"""
    result = {"status": "unknown", "details": []}

    critical_modules = [
        ("signal_live", "signal_live"),
        ("src.telegram.bot_core", "Telegram Bot"),
        ("src.ai.system_manager", "AI System"),
        ("src.database.db", "Database"),
        ("observability", "Observability"),
    ]

    failed = []
    for module_name, display_name in critical_modules:
        try:
            __import__(module_name)
            result["details"].append(f"✅ {display_name}: импорт успешен")
        except ImportError as e:
            failed.append(display_name)
            result["details"].append(f"❌ {display_name}: ошибка импорта - {e}")
        except Exception as e:
            failed.append(display_name)
            result["details"].append(f"⚠️ {display_name}: предупреждение - {e}")

    if len(failed) == 0:
        result["status"] = "ok"
    elif len(failed) < len(critical_modules) / 2:
        result["status"] = "warning"
    else:
        result["status"] = "error"

    return result


def check_config() -> Dict[str, Any]:
    """Проверка конфигурации"""
    result = {"status": "unknown", "details": []}

    config_file = "config.py"
    env_file = "env"

    if os.path.exists(config_file):
        result["details"].append(f"✅ {config_file}: найден")
    else:
        result["details"].append(f"⚠️ {config_file}: не найден")

    if os.path.exists(env_file):
        result["details"].append(f"✅ {env_file}: найден")
        # Проверяем ключевые переменные
        try:
            with open(env_file) as f:
                content = f.read()
                if "TOKEN" in content or "TELEGRAM" in content:
                    result["details"].append("✅ Telegram токен: настроен")
                else:
                    result["details"].append("⚠️ Telegram токен: не найден в env")
        except Exception:
            pass
    else:
        result["details"].append(f"⚠️ {env_file}: не найден")

    result["status"] = "ok"
    return result


def check_files() -> Dict[str, Any]:
    """Проверка критичных файлов"""
    result = {"status": "unknown", "details": []}

    critical_files = [
        "main.py",
        "signal_live.py",
        "src/telegram/bot_core.py",
        "src/database/db.py",
        "observability/__init__.py",
    ]

    missing = []
    for file_path in critical_files:
        if os.path.exists(file_path):
            result["details"].append(f"✅ {file_path}: найден")
        else:
            missing.append(file_path)
            result["details"].append(f"❌ {file_path}: не найден")

    if len(missing) == 0:
        result["status"] = "ok"
    elif len(missing) < len(critical_files) / 2:
        result["status"] = "warning"
    else:
        result["status"] = "error"

    return result


def main():
    """Главная функция проверки"""
    print("🔍 ПРОВЕРКА СТАТУСА СИСТЕМЫ ATRA")
    print("=" * 60)
    print(f"Дата проверки: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    checks = {
        "Процессы": check_processes(),
        "База данных": check_database(),
        "Логи": check_logs(),
        "Импорты": check_imports(),
        "Конфигурация": check_config(),
        "Файлы": check_files(),
    }

    overall_status = "ok"

    for name, result in checks.items():
        status_icon = {"ok": "✅", "warning": "⚠️", "error": "❌", "unknown": "❓"}.get(
            result["status"], "❓"
        )

        print(f"{status_icon} {name}: {result['status'].upper()}")

        for detail in result.get("details", []):
            print(f"   {detail}")

        if result["status"] == "error":
            overall_status = "error"
        elif result["status"] == "warning" and overall_status == "ok":
            overall_status = "warning"

        print()

    # Дополнительная информация
    if "error_count" in checks["Логи"]:
        error_count = checks["Логи"]["error_count"]
        if error_count > 0:
            print(f"📊 Статистика ошибок: {error_count} найдено в последних 100 строках логов")

    # Итоговый статус
    print("=" * 60)
    overall_icon = {"ok": "✅", "warning": "⚠️", "error": "❌"}.get(overall_status, "❓")

    print(f"{overall_icon} ИТОГОВЫЙ СТАТУС: {overall_status.upper()}")

    if overall_status == "ok":
        print("✅ Все системы работают нормально")
    elif overall_status == "warning":
        print("⚠️ Обнаружены предупреждения, но система может работать")
    else:
        print("❌ Обнаружены критические ошибки!")

    return 0 if overall_status in ("ok", "warning") else 1


if __name__ == "__main__":
    sys.exit(main())
