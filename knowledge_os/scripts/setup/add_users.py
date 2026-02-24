#!/usr/bin/env python3
"""
Скрипт для добавления пользователей в базу данных
Использование: python3 add_users.py
"""

import sys

from src.database.db import Database

# Список пользователей для добавления (замените на реальные ID)
# Формат: {user_id: {настройки}}
USERS_TO_ADD = {
    # Пример - замените на реальные ID
    # "123456789": {
    #     "deposit": 10000,
    #     "balance": 10000,
    #     "risk_pct": 2.0,
    #     "risk_amount": 200,
    #     "trade_mode": "futures",  # или "spot"
    #     "filter_mode": "soft",    # или "strict", "balanced"
    #     "leverage": 1,
    #     "positions": [],
    #     "trade_history": [],
    #     "pending_dca": []
    # },
}


def add_users():
    """Добавляет пользователей в базу данных"""
    if not USERS_TO_ADD:
        print("⚠️ Список пользователей пуст. Отредактируйте USERS_TO_ADD в скрипте.")
        return

    db = Database()
    added = 0
    skipped = 0

    print(f"📋 Добавление {len(USERS_TO_ADD)} пользователей...")

    for user_id, user_data in USERS_TO_ADD.items():
        try:
            # Проверяем, существует ли пользователь
            existing = db.get_user_data(user_id)
            if existing:
                print(f"⏭️  Пользователь {user_id} уже существует, пропускаем")
                skipped += 1
                continue

            # Добавляем пользователя
            db.save_user_data(user_id, user_data)
            print(
                f"✅ Пользователь {user_id} добавлен: deposit={user_data.get('deposit')}, mode={user_data.get('trade_mode')}"
            )
            added += 1

        except Exception as e:
            print(f"❌ Ошибка при добавлении пользователя {user_id}: {e}")

    print(f"\n📊 Итого: добавлено {added}, пропущено {skipped}")

    # Показываем всех пользователей
    all_users = db.get_all_users()
    print(f"\n📋 Всего пользователей в системе: {len(all_users)}")
    for uid in all_users:
        user_data = db.get_user_data(uid)
        if user_data:
            print(
                f"  - {uid}: deposit={user_data.get('deposit')}, mode={user_data.get('trade_mode')}, leverage={user_data.get('leverage')}"
            )


if __name__ == "__main__":
    add_users()
