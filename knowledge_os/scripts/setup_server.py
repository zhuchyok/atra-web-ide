#!/usr/bin/env python3

"""
🚀 СКРИПТ НАСТРОЙКИ СЕРВЕРА ATRA
Быстрая настройка и инициализация торгового бота на новом сервере
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_directories():
    """Создает необходимые директории"""
    directories = [
        "backups",
        "logs",
        "cache",
        "ai_learning_data",
        "ai_position_data",
        "ai_tp_data",
        "ai_reports",
        "locales",
    ]

    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"✅ Создана директория: {directory}")
        except OSError as e:
            logger.error(f"❌ Ошибка создания директории {directory}: {e}")


def create_env_file():
    """Создает файл .env если его нет"""
    env_file = Path(".env")

    if env_file.exists():
        logger.info("✅ Файл .env уже существует")
        return

    env_template = """# Конфигурация ATRA Trading Bot
# Скопируйте этот файл и заполните своими данными

# Telegram Bot Token (обязательно)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Режим работы (dev/prod)
ATRA_ENV=dev

# API ключи (опционально)
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key

# Дополнительные настройки
AUTO_FETCH_COINS=true
USE_BTC_TREND_FILTER=true
"""

    try:
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(env_template)
        logger.info("✅ Создан файл .env (заполните своими данными)")
    except OSError as e:
        logger.error(f"❌ Ошибка создания файла .env: {e}")


def check_python_dependencies():
    """Проверяет наличие необходимых Python пакетов"""
    required_packages = [
        "telegram",
        "pandas",
        "numpy",
        "requests",
        "aiohttp",
        "python-dotenv",
        "sqlite3",
    ]

    missing_packages = []

    for package in required_packages:
        try:
            if package == "python-dotenv":
                import dotenv
            elif package == "telegram":
                import telegram
            elif package == "sqlite3":
                import sqlite3
            else:
                __import__(package)
            logger.info(f"✅ Пакет {package} установлен")
        except ImportError:
            missing_packages.append(package)
            logger.warning(f"⚠️ Пакет {package} не найден")

    if missing_packages:
        logger.error(f"❌ Отсутствуют пакеты: {', '.join(missing_packages)}")
        logger.info("💡 Установите их командой: pip install " + " ".join(missing_packages))
        return False

    return True


async def initialize_database():
    """Инициализирует базу данных"""
    try:
        from db_init import DatabaseInitializer

        logger.info("🔄 Инициализация базы данных...")
        initializer = DatabaseInitializer()

        # Пытаемся инициализировать с данными
        success = await initializer.initialize_database(with_data=True)

        if not success:
            logger.warning("⚠️ Инициализация с данными не удалась, создаем только структуру...")
            success = await initializer.initialize_database(with_data=False)

        if success:
            logger.info("✅ База данных инициализирована успешно")
            return True
        else:
            logger.error("❌ Ошибка инициализации базы данных")
            return False

    except ImportError:
        logger.warning("⚠️ Модуль db_init недоступен, используем стандартную инициализацию...")
        try:
            from db import Database

            db = Database()
            logger.info("✅ База данных инициализирована через стандартный механизм")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {e}")
        return False


def create_user_data_file():
    """Создает файл user_data.json если его нет"""
    user_data_file = Path("user_data.json")

    if user_data_file.exists():
        logger.info("✅ Файл user_data.json уже существует")
        return

    default_user_data = {
        "users": {},
        "settings": {
            "default_filter_mode": "strict",
            "default_trade_mode": "spot",
            "default_risk_pct": 2.0,
            "default_leverage": 1.0,
        },
    }

    try:
        import json

        with open(user_data_file, "w", encoding="utf-8") as f:
            json.dump(default_user_data, f, ensure_ascii=False, indent=2)
        logger.info("✅ Создан файл user_data.json")
    except OSError as e:
        logger.error(f"❌ Ошибка создания файла user_data.json: {e}")


def create_locale_files():
    """Создает файлы локализации"""
    locales_dir = Path("locales")
    locales_dir.mkdir(exist_ok=True)

    # Русская локализация
    ru_locale = {
        "welcome": "Добро пожаловать в ATRA Trading Bot!",
        "help": "Помощь",
        "balance": "Баланс",
        "positions": "Позиции",
        "settings": "Настройки",
    }

    # Английская локализация
    en_locale = {
        "welcome": "Welcome to ATRA Trading Bot!",
        "help": "Help",
        "balance": "Balance",
        "positions": "Positions",
        "settings": "Settings",
    }

    for lang, content in [("ru", ru_locale), ("en", en_locale)]:
        locale_file = locales_dir / f"{lang}.json"
        if not locale_file.exists():
            try:
                import json

                with open(locale_file, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ Создан файл локализации: {locale_file}")
            except OSError as e:
                logger.error(f"❌ Ошибка создания файла локализации {lang}: {e}")


async def main():
    """Основная функция настройки сервера"""
    logger.info("🚀 Начинаем настройку сервера ATRA...")

    # 1. Создаем необходимые директории
    logger.info("📁 Создание директорий...")
    create_directories()

    # 2. Проверяем зависимости
    logger.info("📦 Проверка зависимостей...")
    if not check_python_dependencies():
        logger.error("❌ Не все зависимости установлены. Завершаем настройку.")
        return False

    # 3. Создаем файл .env
    logger.info("⚙️ Создание конфигурационного файла...")
    create_env_file()

    # 4. Создаем файл пользовательских данных
    logger.info("👥 Создание файла пользовательских данных...")
    create_user_data_file()

    # 5. Создаем файлы локализации
    logger.info("🌍 Создание файлов локализации...")
    create_locale_files()

    # 6. Инициализируем базу данных
    logger.info("🗄️ Инициализация базы данных...")
    db_success = await initialize_database()

    if db_success:
        logger.info("🎉 Настройка сервера завершена успешно!")
        logger.info("")
        logger.info("📋 Следующие шаги:")
        logger.info("1. Отредактируйте файл .env и добавьте свой Telegram Bot Token")
        logger.info("2. Запустите бота командой: python3 main.py")
        logger.info("3. Проверьте логи в файле system_improved.log")
        logger.info("")
        logger.info("🔧 Для ручной инициализации базы данных используйте:")
        logger.info("   python3 db_init.py")
        logger.info("   python3 init_db.py")
        return True
    else:
        logger.error("💥 Настройка сервера завершилась с ошибками!")
        logger.info("")
        logger.info("🔧 Попробуйте запустить инициализацию базы данных вручную:")
        logger.info("   python3 db_init.py --structure-only")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("🛑 Настройка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Неожиданная ошибка: {e}")
        sys.exit(1)
