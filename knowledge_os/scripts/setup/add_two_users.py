#!/usr/bin/env python3
"""Добавление двух пользователей: 958930260 и 556251171"""

import sys
import os
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Прямое подключение к БД для надежности
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'trading.db')

# Пользователь 1: 958930260
user_1_id = "958930260"
user_1_data = {
    "deposit": 10000.0,
    "balance": 10000.0,
    "free_deposit": 10000.0,
    "risk_pct": 2.0,
    "trade_mode": "futures",
    "filter_mode": "soft",
    "auto_mode": "auto",
    "leverage": 5,
    "setup_completed": True,
    "total_risk_amount": 0,
    "total_profit": 0,
    "open_positions": [],
    "accepted_signals": [],
    "trade_history": [],
    "news_filter_mode": "aggressive",
    "positions": []
}

# Пользователь 2: 556251171
user_2_id = "556251171"
user_2_data = {
    "deposit": 6500.0,
    "balance": 6500.0,
    "free_deposit": 6500.0,
    "risk_pct": 2.0,
    "trade_mode": "futures",
    "filter_mode": "soft",
    "auto_mode": "auto",
    "leverage": 5,
    "setup_completed": True,
    "total_risk_amount": 0,
    "total_profit": 0,
    "open_positions": [],
    "accepted_signals": [],
    "trade_history": [],
    "news_filter_mode": "aggressive",
    "positions": []
}

print("=" * 60)
print("ДОБАВЛЕНИЕ ДВУХ ПОЛЬЗОВАТЕЛЕЙ")
print("=" * 60)

# Прямое сохранение в БД
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Создаем таблицу если её нет
cur.execute("""
    CREATE TABLE IF NOT EXISTS users_data (
        user_id TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
""")
conn.commit()

# Добавляем пользователя 1
print(f"\n👤 Пользователь 1: {user_1_id}")
try:
    cur.execute("SELECT data FROM users_data WHERE user_id = ?", (user_1_id,))
    row = cur.fetchone()
    if row:
        existing_data = json.loads(row[0])
        print(f"  ⚠️  Уже существует")
        print(f"     deposit: {existing_data.get('deposit', 'N/A')}")
        print(f"     trade_mode: {existing_data.get('trade_mode', 'N/A')}")
        print(f"     leverage: {existing_data.get('leverage', 'N/A')}")
    else:
        cur.execute(
            "INSERT OR REPLACE INTO users_data (user_id, data, updated_at) VALUES (?, ?, ?)",
            (user_1_id, json.dumps(user_1_data), datetime.now().isoformat())
        )
        conn.commit()
        print(f"  ✅ Добавлен")
        print(f"     deposit: {user_1_data['deposit']}")
        print(f"     trade_mode: {user_1_data['trade_mode']}")
        print(f"     leverage: {user_1_data['leverage']}x")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

# Добавляем пользователя 2
print(f"\n👤 Пользователь 2: {user_2_id}")
try:
    cur.execute("SELECT data FROM users_data WHERE user_id = ?", (user_2_id,))
    row = cur.fetchone()
    if row:
        existing_data = json.loads(row[0])
        print(f"  ⚠️  Уже существует")
        print(f"     deposit: {existing_data.get('deposit', 'N/A')}")
        print(f"     trade_mode: {existing_data.get('trade_mode', 'N/A')}")
        print(f"     leverage: {existing_data.get('leverage', 'N/A')}")
    else:
        cur.execute(
            "INSERT OR REPLACE INTO users_data (user_id, data, updated_at) VALUES (?, ?, ?)",
            (user_2_id, json.dumps(user_2_data), datetime.now().isoformat())
        )
        conn.commit()
        print(f"  ✅ Добавлен")
        print(f"     deposit: {user_2_data['deposit']}")
        print(f"     trade_mode: {user_2_data['trade_mode']}")
        print(f"     leverage: {user_2_data['leverage']}x")
except Exception as e:
    print(f"  ❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()

# Финальная проверка
print("\n" + "=" * 60)
print("ФИНАЛЬНАЯ ПРОВЕРКА")
print("=" * 60)
cur.execute("SELECT user_id, data FROM users_data")
rows = cur.fetchall()
print(f"\n📊 Всего пользователей в системе: {len(rows)}")
for uid, data_json in rows:
    try:
        user_data = json.loads(data_json)
        deposit = user_data.get("deposit", 0)
        mode = user_data.get("trade_mode", "unknown")
        leverage = user_data.get("leverage", 1)
        risk_pct = user_data.get("risk_pct", 0)
        print(f"  👤 {uid}:")
        print(f"     💰 deposit: {deposit}")
        print(f"     📊 trade_mode: {mode}")
        print(f"     ⚡ leverage: {leverage}x")
        print(f"     📈 risk_pct: {risk_pct}%")
    except:
        print(f"  👤 {uid}: (ошибка парсинга данных)")

conn.close()

if len(rows) == 2:
    print("\n✅ Оба пользователя успешно добавлены!")
else:
    print(f"\n⚠️  Ожидалось 2 пользователя, найдено {len(rows)}")

