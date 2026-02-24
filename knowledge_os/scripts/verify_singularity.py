#!/usr/bin/env python3
"""
Проверка готовности Singularity 8.0 к запуску
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


def check_imports():
    """Проверяет, что все модули можно импортировать"""
    print("🔍 Проверка импортов модулей...\n")

    modules = [
        "parallel_request_processor",
        "ml_router_v2",
        "session_context_manager",
        "rate_limiter",
        "secret_manager",
        "metrics_exporter",
        "usage_analytics",
        "report_generator",
        "file_processor",
        "voice_processor",
        "external_api_integration",
        "health_check",
        "embedding_optimizer",
        "cache_cleanup_task",
        "ml_router_trainer",
        "ml_router_data_collector",
    ]

    failed = []
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except Exception as e:
            print(f"  ❌ {module}: {e}")
            failed.append(module)

    return len(failed) == 0


def check_directory_structure():
    """Проверяет структуру директорий"""
    print("\n📁 Проверка структуры директорий...\n")

    dirs = [
        "knowledge_os/app",
        "knowledge_os/db/migrations",
        "knowledge_os/scripts",
        "docs",
        "logs",
    ]

    failed = []
    for dir_path in dirs:
        full_path = Path(__file__).parent.parent.parent / dir_path
        if full_path.exists():
            print(f"  ✅ {dir_path}")
        else:
            print(f"  ❌ {dir_path} - не существует")
            failed.append(dir_path)

    return len(failed) == 0


def check_env_file():
    """Проверяет наличие .env файла"""
    print("\n🔐 Проверка переменных окружения...\n")

    env_file = Path(__file__).parent.parent.parent / ".env"
    if env_file.exists():
        print("  ✅ .env файл существует")
        return True
    else:
        print("  ⚠️ .env файл не найден (создайте через setup_environment.py)")
        return False


def main():
    """Основная функция проверки"""
    print("🔍 Singularity 8.0: Проверка готовности\n")
    print("=" * 50)
    print()

    results = []

    # Проверка импортов
    results.append(("Импорты модулей", check_imports()))

    # Проверка структуры директорий
    results.append(("Структура директорий", check_directory_structure()))

    # Проверка .env файла
    results.append(("Переменные окружения", check_env_file()))

    # Итоговая сводка
    print("\n" + "=" * 50)
    print("📊 Итоговая сводка:\n")

    all_ok = True
    for name, status in results:
        status_str = "✅ OK" if status else "❌ FAILED"
        print(f"  {status_str}: {name}")
        if not status:
            all_ok = False

    print()
    if all_ok:
        print("✅ Все проверки пройдены! Система готова к запуску.")
        return 0
    else:
        print("⚠️ Некоторые проверки провалены. Исправьте проблемы выше.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
