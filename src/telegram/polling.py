#!/usr/bin/env python3
"""
Скрипт для принудительного запуска Telegram Bot в режиме polling
"""

import asyncio
import logging
import os
import sys

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


async def start_telegram_polling():
    """Запускает Telegram Bot в режиме polling"""

    print("🚀 ЗАПУСК TELEGRAM BOT В РЕЖИМЕ POLLING")
    print("=" * 50)

    try:
        # Удаляем lock файл если есть
        import glob

        lock_files = glob.glob("/tmp/atra_tg_poll_*.lock")
        for lock_file in lock_files:
            try:
                os.remove(lock_file)
                print(f"✅ Удален lock файл: {lock_file}")
            except Exception as e:
                print(f"⚠️ Не удалось удалить {lock_file}: {e}")

        # Импортируем и запускаем Telegram Bot
        print("\n1️⃣ Импорт src.telegram.bot_core...")
        from src.telegram.bot_core import run_telegram_bot_in_existing_loop

        print("2️⃣ Запуск Telegram Bot в режиме polling...")
        await run_telegram_bot_in_existing_loop()

    except Exception as e:
        logger.error(f"❌ Ошибка запуска Telegram Bot: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🎯 Запуск Telegram Bot для обработки callback queries...")
    asyncio.run(start_telegram_polling())
