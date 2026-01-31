#!/usr/bin/env python3
"""
Скрипт для установки режима 'auto' только для пользователей с ключами биржи
"""

import sqlite3
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def set_auto_mode_for_users_with_keys():
    """Устанавливает режим 'auto' только для пользователей с активными ключами биржи"""
    
    # Путь к БД
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trading.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Проверка пользователей с ключами биржи...")
        
        # 1. Проверяем наличие таблицы user_exchange_keys
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_exchange_keys'
        """)
        if not cursor.fetchone():
            print("⚠️ Таблица user_exchange_keys не найдена. Создаем...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_exchange_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exchange_name TEXT NOT NULL,
                    api_key TEXT,
                    secret_key TEXT,
                    passphrase TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, exchange_name)
                )
            """)
            conn.commit()
            print("✅ Таблица user_exchange_keys создана")
        
        # 2. Проверяем наличие таблицы user_settings
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_settings'
        """)
        if not cursor.fetchone():
            print("⚠️ Таблица user_settings не найдена. Создаем...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    trade_mode TEXT DEFAULT 'manual',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            print("✅ Таблица user_settings создана")
        
        # 3. Получаем список пользователей с активными ключами
        cursor.execute("""
            SELECT DISTINCT user_id, exchange_name
            FROM user_exchange_keys
            WHERE is_active = 1
            ORDER BY user_id, exchange_name
        """)
        users_with_keys = cursor.fetchall()
        
        if not users_with_keys:
            print("⚠️ Нет пользователей с активными ключами биржи")
            print("   Установите ключи через команду Telegram или вручную в БД")
            return False
        
        print(f"\n✅ Найдено пользователей с ключами: {len(users_with_keys)}")
        for user_id, exchange in users_with_keys:
            print(f"   - Пользователь {user_id}: {exchange}")
        
        # 4. Устанавливаем режим 'auto' для пользователей с ключами
        cursor.execute("""
            INSERT OR REPLACE INTO user_settings (user_id, trade_mode, updated_at)
            SELECT DISTINCT user_id, 'auto', CURRENT_TIMESTAMP
            FROM user_exchange_keys
            WHERE is_active = 1
        """)
        affected_auto = cursor.rowcount
        
        # 5. Устанавливаем режим 'manual' для пользователей БЕЗ ключей
        # (если они есть в списке известных пользователей)
        known_users = [556251171, 958930260]
        for user_id in known_users:
            cursor.execute("""
                SELECT COUNT(*) FROM user_exchange_keys
                WHERE user_id = ? AND is_active = 1
            """, (user_id,))
            has_keys = cursor.fetchone()[0] > 0
            
            if not has_keys:
                cursor.execute("""
                    INSERT OR REPLACE INTO user_settings (user_id, trade_mode, updated_at)
                    VALUES (?, 'manual', CURRENT_TIMESTAMP)
                """, (user_id,))
        
        conn.commit()
        
        # 6. Проверяем результат
        cursor.execute("""
            SELECT s.user_id, s.trade_mode, 
                   CASE WHEN EXISTS (
                       SELECT 1 FROM user_exchange_keys k 
                       WHERE k.user_id = s.user_id AND k.is_active = 1
                   ) THEN '✅ Есть ключи' ELSE '❌ Нет ключей' END as keys_status
            FROM user_settings s
            ORDER BY s.user_id
        """)
        results = cursor.fetchall()
        
        print(f"\n📊 Результаты установки режимов:")
        print("-" * 60)
        for user_id, mode, keys_status in results:
            status_icon = "✅" if mode == 'auto' else "❌"
            print(f"{status_icon} Пользователь {user_id}: {mode.upper()} ({keys_status})")
        
        print(f"\n✅ Установлено режимов 'auto': {affected_auto}")
        print("✅ Готово!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 УСТАНОВКА РЕЖИМА 'AUTO' ДЛЯ ПОЛЬЗОВАТЕЛЕЙ С КЛЮЧАМИ БИРЖИ")
    print("=" * 60)
    print()
    
    success = set_auto_mode_for_users_with_keys()
    
    sys.exit(0 if success else 1)

