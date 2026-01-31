#!/usr/bin/env python3
"""Добавление второго пользователя 958930260"""

from src.database.db import Database

db = Database()

# Второй пользователь из документации
user_2_id = "958930260"
user_2_data = {
    "deposit": 200.0,
    "balance": 200.0,
    "free_deposit": 200.0,
    "risk_pct": 2.0,
    "trade_mode": "futures",
    "filter_mode": "soft",
    "auto_mode": "auto",
    "leverage": 3,
    "setup_completed": True,
    "total_risk_amount": 0,
    "total_profit": 0,
    "open_positions": [],
    "accepted_signals": [],
    "trade_history": [],
    "news_filter_mode": "aggressive",
    "positions": []
}

# Проверяем, существует ли уже
existing = db.get_user_data(user_2_id)
if existing:
    print(f"⚠️  Пользователь {user_2_id} уже существует")
    deposit_val = existing.get("deposit", 0)
    mode_val = existing.get("trade_mode", "unknown")
    print(f"   Депозит: {deposit_val}, Режим: {mode_val}")
else:
    # Добавляем
    db.save_user_data(user_2_id, user_2_data)
    print(f"✅ Пользователь {user_2_id} добавлен")
    deposit = user_2_data["deposit"]
    mode = user_2_data["trade_mode"]
    leverage = user_2_data["leverage"]
    print(f"   Депозит: {deposit}, Режим: {mode}, Плечо: {leverage}x")

# Проверяем всех пользователей
all_users = db.get_all_users()
print(f"\n📊 Всего пользователей в системе: {len(all_users)}")
for uid in all_users:
    user_data = db.get_user_data(uid)
    if user_data:
        deposit = user_data.get("deposit", 0)
        mode = user_data.get("trade_mode", "unknown")
        leverage = user_data.get("leverage", 1)
        print(f"  ✅ {uid}: deposit={deposit}, mode={mode}, leverage={leverage}x")

