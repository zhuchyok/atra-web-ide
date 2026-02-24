#!/usr/bin/env python3
"""
Проверка готовности системы Singularity 8.0 к запуску
"""

import asyncio
import os
import sys
from pathlib import Path

# Добавляем путь к knowledge_os
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))


def check_dependencies():
    """Проверяет установленные зависимости"""
    print("🔍 Проверка зависимостей...")

    dependencies = {
        "httpx": "httpx",
        "asyncpg": "asyncpg",
        "aiohttp": "aiohttp",
        "pandas": "pandas",
        "sklearn": "scikit-learn",
        "cryptography": "cryptography",
    }

    missing = []
    for module, package in dependencies.items():
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - НЕ УСТАНОВЛЕН")
            missing.append(package)

    if missing:
        print("\n⚠️ Установите недостающие зависимости:")
        print(f"pip install {' '.join(missing)}")
        return False
    return True


def check_environment_variables():
    """Проверяет переменные окружения"""
    print("\n🔍 Проверка переменных окружения...")

    optional = ["OPENAI_API_KEY", "DATABASE_URL", "GITHUB_TOKEN", "USE_OPENAI_WHISPER"]

    all_ok = True

    # Проверка TG_TOKEN (критично, но может быть в коде)
    tg_token = os.getenv("TG_TOKEN")
    if tg_token:
        print("  ✅ TG_TOKEN - установлена в переменных окружения")
    else:
        # Проверяем, есть ли TG_TOKEN в коде telegram_simple.py (fallback)
        telegram_file = Path(__file__).parent.parent / "app" / "telegram_simple.py"
        if telegram_file.exists():
            import re

            content = telegram_file.read_text()
            tg_token_match = re.search(r'TG_TOKEN\s*=\s*"([^"]+)"', content)
            if tg_token_match:
                print("  ✅ TG_TOKEN - найдена в коде telegram_simple.py")
            else:
                print("  ❌ TG_TOKEN - НЕ УСТАНОВЛЕНА (критично!)")
                all_ok = False
        else:
            print("  ❌ TG_TOKEN - НЕ УСТАНОВЛЕНА (критично!)")
            all_ok = False

    for var in optional:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var} - установлена")
        else:
            print(f"  ⚠️ {var} - не установлена (опционально)")

    return all_ok


async def check_database():
    """Проверяет подключение к базе данных"""
    print("\n🔍 Проверка базы данных...")

    try:
        import getpass

        import asyncpg

        USER_NAME = getpass.getuser()
        db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

        conn = await asyncpg.connect(db_url)
        try:
            # Проверяем таблицы
            tables = [
                "semantic_ai_cache",
                "session_context",
                "user_feedback",
                "ml_routing_training_data",
            ]

            for table in tables:
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = $1
                    )
                """,
                    table,
                )
                if exists:
                    print(f"  ✅ Таблица {table} существует")
                else:
                    print(f"  ❌ Таблица {table} НЕ существует")

            # Проверяем миграции
            count = await conn.fetchval("SELECT COUNT(*) FROM schema_migrations")
            print(f"  ✅ Применено миграций: {count}")

            return True
        finally:
            await conn.close()
    except Exception as e:
        print(f"  ❌ Ошибка подключения к БД: {e}")
        return False


def check_modules():
    """Проверяет наличие всех модулей"""
    print("\n🔍 Проверка модулей...")

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
    ]

    all_ok = True
    for module in modules:
        module_path = Path(__file__).parent.parent / "app" / f"{module}.py"
        if module_path.exists():
            print(f"  ✅ {module}.py")
        else:
            print(f"  ❌ {module}.py - НЕ НАЙДЕН")
            all_ok = False

    return all_ok


async def main():
    """Главная функция проверки"""
    print("🚀 Проверка готовности системы Singularity 8.0\n")
    print("=" * 60)

    results = {
        "dependencies": check_dependencies(),
        "environment": check_environment_variables(),
        "database": await check_database(),
        "modules": check_modules(),
    }

    print("\n" + "=" * 60)
    print("\n📊 Итоговый статус:")

    all_ready = all(results.values())

    if all_ready:
        print("✅ Система готова к запуску!")
        print("\nЗапуск:")
        print("  python knowledge_os/app/telegram_simple.py")
        print("  python knowledge_os/app/singularity_autonomous.py")
        return 0
    else:
        print("⚠️ Система не готова. Исправьте проблемы выше.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
