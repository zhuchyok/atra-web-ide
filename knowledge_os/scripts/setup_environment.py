#!/usr/bin/env python3
"""
Настройка переменных окружения для Singularity 8.0
Создает .env файл с шаблонами или проверяет существующие
"""

import os
from pathlib import Path


def setup_environment():
    """Настраивает переменные окружения"""
    print("🔧 Настройка переменных окружения...\n")

    # Путь к .env файлу
    env_file = Path(__file__).parent.parent.parent / ".env"
    env_example = Path(__file__).parent.parent.parent / ".env.example"

    # Проверяем существующие переменные
    print("📋 Проверка существующих переменных окружения:")

    env_vars = {
        "TG_TOKEN": os.getenv("TG_TOKEN"),
        "TG_TOKEN_DEV": os.getenv("TG_TOKEN_DEV"),
        "TG_TOKEN_PROD": os.getenv("TG_TOKEN_PROD"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN"),
        "USE_OPENAI_WHISPER": os.getenv("USE_OPENAI_WHISPER", "false"),
    }

    all_set = True
    for var, value in env_vars.items():
        if value:
            print(f"  ✅ {var} - установлена")
        else:
            print(f"  ⚠️ {var} - не установлена")
            if var in ["TG_TOKEN", "OPENAI_API_KEY"]:
                all_set = False

    # Создаем .env.example если его нет
    if not env_example.exists():
        print(f"\n📝 Создание {env_example}...")
        env_example.write_text("""# Singularity 8.0 Environment Variables

# Telegram Bot Tokens
TG_TOKEN=your_telegram_bot_token
TG_TOKEN_DEV=your_dev_telegram_bot_token
TG_TOKEN_PROD=your_prod_telegram_bot_token

# OpenAI API
OPENAI_API_KEY=your_openai_api_key
USE_OPENAI_WHISPER=false

# Database
DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os

# External APIs (optional)
GITHUB_TOKEN=your_github_token

# Secret Manager (optional)
SECRET_MASTER_KEY=your_secret_master_key
""")
        print(f"  ✅ {env_example} создан")

    # Если .env не существует, создаем из примера
    if not env_file.exists() and env_example.exists():
        print(f"\n📝 Создание {env_file} из примера...")
        import shutil

        shutil.copy(env_example, env_file)
        print(f"  ✅ {env_file} создан")
        print(f"  ⚠️ ВАЖНО: Отредактируйте {env_file} и укажите реальные значения!")
        all_set = False

    if all_set:
        print("\n✅ Все критичные переменные окружения установлены!")
        return True
    else:
        print("\n⚠️ Некоторые переменные окружения не установлены.")
        print(f"   Отредактируйте {env_file} или установите переменные окружения.")
        return False


if __name__ == "__main__":
    setup_environment()
