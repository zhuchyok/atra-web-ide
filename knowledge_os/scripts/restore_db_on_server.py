#!/usr/bin/env python3
"""
Скрипт восстановления БД для запуска на сервере
Можно запустить: python3 restore_db_on_server.py
"""

import os
import shutil
import sqlite3
import sys
from datetime import datetime

from src.shared.utils.datetime_utils import get_utc_now

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

db_path = "/root/atra/trading.db"
backup_dir = "/root/atra/backups"
os.makedirs(backup_dir, exist_ok=True)

print("=" * 80)
print("🔧 ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ")
print("=" * 80)

if not os.path.exists(db_path):
    print("❌ БД не найдена, создаем новую...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY, symbol TEXT, signal_type TEXT,
        entry_price REAL, status TEXT DEFAULT 'active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS active_signals (
        id INTEGER PRIMARY KEY, symbol TEXT, signal_type TEXT,
        entry_price REAL, status TEXT DEFAULT 'active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, user_id TEXT UNIQUE, username TEXT,
        is_active BOOLEAN DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()
    print("✅ Новая БД создана")
else:
    print("📦 Создание бэкапа...")
    timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"trading_db_backup_{timestamp}.db")
    shutil.copy2(db_path, backup_path)
    print(f"✅ Бэкап создан: {backup_path}")

    print("🔍 Проверка целостности...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()

        if result and result[0] == "ok":
            print("✅ База данных целостна")
        else:
            print(f"❌ БД повреждена: {result}")
            print("🔧 Попытка восстановления...")
            recovered_path = db_path + ".recovered"
            try:
                conn = sqlite3.connect(db_path)
                recovered_conn = sqlite3.connect(recovered_path)
                conn.backup(recovered_conn)
                conn.close()
                recovered_conn.close()

                test_conn = sqlite3.connect(recovered_path)
                test_cursor = test_conn.cursor()
                test_cursor.execute("PRAGMA integrity_check")
                test_result = test_cursor.fetchone()
                test_conn.close()

                if test_result and test_result[0] == "ok":
                    shutil.move(recovered_path, db_path)
                    print("✅ БД восстановлена")
                else:
                    os.remove(recovered_path)
                    print("❌ Восстановление не удалось, пересоздаем структуру...")
                    os.remove(db_path)
                    new_conn = sqlite3.connect(db_path)
                    new_cursor = new_conn.cursor()
                    new_cursor.execute("""CREATE TABLE IF NOT EXISTS signals (
                        id INTEGER PRIMARY KEY, symbol TEXT, signal_type TEXT,
                        entry_price REAL, status TEXT DEFAULT 'active',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
                    new_cursor.execute("""CREATE TABLE IF NOT EXISTS active_signals (
                        id INTEGER PRIMARY KEY, symbol TEXT, signal_type TEXT,
                        entry_price REAL, status TEXT DEFAULT 'active',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
                    new_cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY, user_id TEXT UNIQUE, username TEXT,
                        is_active BOOLEAN DEFAULT 1, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
                    new_conn.commit()
                    new_conn.close()
                    print("✅ Структура пересоздана")
            except Exception as e:
                print(f"❌ Ошибка восстановления: {e}")
                if os.path.exists(recovered_path):
                    os.remove(recovered_path)
    except Exception as e:
        print(f"❌ Ошибка: {e}")

    print("🔍 Финальная проверка...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        if result and result[0] == "ok":
            print("✅ БД целостна и готова к работе")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"📊 Таблиц: {len(tables)}")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("❌ БД все еще повреждена")
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка: {e}")

print("=" * 80)
print("✅ ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО")
print("=" * 80)
