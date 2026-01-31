#!/usr/bin/env python3
"""Скрипт для сброса ключей Bitget и режима пользователя"""

import sqlite3
import sys

def reset_bitget_keys(user_id=None):
    """Удаляет все ключи Bitget и переводит пользователей в manual режим"""
    try:
        conn = sqlite3.connect('trading.db')
        cursor = conn.cursor()
        
        # Создаём таблицы если не существуют
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_exchange_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exchange_name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                secret_key TEXT NOT NULL,
                passphrase TEXT,
                is_active INTEGER DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, exchange_name)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                trade_mode TEXT DEFAULT 'manual',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if user_id:
            # Для конкретного пользователя
            cursor.execute("DELETE FROM user_exchange_keys WHERE user_id = ?", (int(user_id),))
            deleted = cursor.rowcount
            cursor.execute("INSERT OR REPLACE INTO user_settings(user_id, trade_mode) VALUES(?, 'manual')", (int(user_id),))
            print(f"✅ Удалено {deleted} ключей для user {user_id}")
            print(f"✅ Режим переключён на manual для user {user_id}")
        else:
            # Для всех пользователей
            cursor.execute("DELETE FROM user_exchange_keys")
            deleted = cursor.rowcount
            cursor.execute("UPDATE user_settings SET trade_mode = 'manual'")
            print(f"✅ Удалено {deleted} ключей Bitget")
            print("✅ Все пользователи переключены на manual")
        
        conn.commit()
        conn.close()
        print("\n🎯 Готово! Теперь переподключите ключи:")
        print("   /connect_bitget <api_key> <secret> <passphrase>")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        reset_bitget_keys(sys.argv[1])
    else:
        reset_bitget_keys()

