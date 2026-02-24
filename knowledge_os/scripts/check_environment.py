#!/usr/bin/env python3
"""
Скрипт для проверки окружения и конфигурации Telegram бота
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


def check_environment():
    """Проверяет конфигурацию окружения"""
    print("=" * 60)
    print("🔍 ПРОВЕРКА ОКРУЖЕНИЯ И КОНФИГУРАЦИИ")
    print("=" * 60)

    # 1. Проверка окружения
    atra_env = os.getenv("ATRA_ENV", "dev").lower().strip()
    print(f"\n📊 Окружение: {atra_env.upper()}")

    if atra_env == "prod":
        print("   ✅ PROD режим - используется TELEGRAM_TOKEN")
    else:
        print("   ⚠️  DEV режим - используется TELEGRAM_TOKEN_DEV")
        print("   💡 Для prod установите: export ATRA_ENV=prod")

    # 2. Проверка токенов
    telegram_token = os.getenv("TELEGRAM_TOKEN", "")
    telegram_token_dev = os.getenv("TELEGRAM_TOKEN_DEV", "")

    print("\n🔑 Токены:")
    if telegram_token:
        token_preview = (
            f"{telegram_token[:10]}...{telegram_token[-10:]}"
            if len(telegram_token) > 20
            else telegram_token
        )
        print(f"   ✅ TELEGRAM_TOKEN (PROD): {token_preview}")
    else:
        print("   ❌ TELEGRAM_TOKEN (PROD): НЕ УСТАНОВЛЕН!")

    if telegram_token_dev:
        token_dev_preview = (
            f"{telegram_token_dev[:10]}...{telegram_token_dev[-10:]}"
            if len(telegram_token_dev) > 20
            else telegram_token_dev
        )
        print(f"   ✅ TELEGRAM_TOKEN_DEV: {token_dev_preview}")
    else:
        print("   ❌ TELEGRAM_TOKEN_DEV: НЕ УСТАНОВЛЕН!")

    # 3. Определяем какой токен будет использоваться
    if atra_env == "prod":
        active_token = telegram_token
        token_name = "TELEGRAM_TOKEN (PROD)"
    else:
        active_token = telegram_token_dev or telegram_token
        token_name = "TELEGRAM_TOKEN_DEV" if telegram_token_dev else "TELEGRAM_TOKEN (fallback)"

    if active_token:
        active_preview = (
            f"{active_token[:10]}...{active_token[-10:]}"
            if len(active_token) > 20
            else active_token
        )
        print(f"\n🎯 Активный токен: {token_name}")
        print(f"   {active_preview}")
    else:
        print("\n❌ ОШИБКА: Нет активного токена!")
        print("   Установите TELEGRAM_TOKEN или TELEGRAM_TOKEN_DEV")
        return False

    # 4. Проверка chat_ids
    chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
    if chat_ids:
        ids_list = [cid.strip() for cid in chat_ids.split(",") if cid.strip()]
        print(f"\n👥 Chat IDs: {len(ids_list)} шт.")
        for cid in ids_list[:5]:  # Показываем первые 5
            print(f"   - {cid}")
        if len(ids_list) > 5:
            print(f"   ... и еще {len(ids_list) - 5}")
    else:
        print("\n⚠️  TELEGRAM_CHAT_IDS: НЕ УСТАНОВЛЕН!")
        print("   Сигналы не будут отправляться никому!")

    # 5. Проверка config.py
    print("\n📋 Проверка config.py:")
    try:
        import config

        print("   ✅ config.py загружен")
        print(f"   ATRA_ENV в config: {getattr(config, 'ATRA_ENV', 'N/A')}")
        print(
            f"   TOKEN в config: {getattr(config, 'TOKEN', 'N/A')[:20]}..."
            if hasattr(config, "TOKEN") and config.TOKEN
            else "   TOKEN: НЕ УСТАНОВЛЕН"
        )
    except Exception as e:
        print(f"   ❌ Ошибка загрузки config.py: {e}")

    # 6. Рекомендации
    print("\n💡 РЕКОМЕНДАЦИИ:")
    if atra_env != "prod":
        print("   1. Для PROD установите: export ATRA_ENV=prod")
        print("   2. Или в файле env установите: ATRA_ENV=prod")

    if not chat_ids:
        print("   3. Установите TELEGRAM_CHAT_IDS в env файле")

    if not active_token:
        print("   4. Установите TELEGRAM_TOKEN или TELEGRAM_TOKEN_DEV")

    print("\n" + "=" * 60)
    return True


if __name__ == "__main__":
    try:
        check_environment()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
