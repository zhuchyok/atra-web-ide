#!/usr/bin/env python3
"""
Скрипт для восстановления зашифрованных ключей из backup БД
"""

import os
import sys
import sqlite3
import shutil
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def restore_keys_from_backup():
    """Восстанавливает ключи из backup БД в основную БД"""
    
    # Путь к основной БД
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trading.db')
    backups_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backups')
    
    if not os.path.exists(backups_dir):
        print(f"❌ Директория backups не найдена: {backups_dir}")
        return False
    
    # Находим все backup файлы
    backup_files = sorted(Path(backups_dir).glob('trading.db_*'), reverse=True)
    
    if not backup_files:
        print("❌ Backup файлы не найдены")
        return False
    
    print(f"🔍 Найдено {len(backup_files)} backup файлов")
    
    # Проверяем каждый backup на наличие ключей
    for backup_file in backup_files:
        print(f"\n📂 Проверка: {backup_file.name}")
        
        try:
            conn = sqlite3.connect(str(backup_file))
            cursor = conn.cursor()
            
            # Проверяем наличие таблицы
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='user_exchange_keys'
            """)
            if not cursor.fetchone():
                print("   ⚠️ Таблица user_exchange_keys не найдена")
                conn.close()
                continue
            
            # Проверяем наличие ключей
            cursor.execute("""
                SELECT user_id, exchange_name, 
                       CASE WHEN api_key IS NOT NULL AND api_key != '' THEN 1 ELSE 0 END as has_key,
                       is_active
                FROM user_exchange_keys
                WHERE api_key IS NOT NULL AND api_key != ''
                ORDER BY updated_at DESC
            """)
            
            keys_found = cursor.fetchall()
            
            if keys_found:
                print(f"   ✅ Найдено {len(keys_found)} записей с ключами!")
                for user_id, exchange, has_key, is_active in keys_found:
                    print(f"      - Пользователь {user_id}, биржа {exchange}, активен: {is_active}")
                
                # Копируем ключи в основную БД
                print(f"\n   🔄 Копирование ключей в основную БД...")
                
                main_conn = sqlite3.connect(db_path)
                main_cursor = main_conn.cursor()
                
                # Получаем зашифрованные ключи из backup
                cursor.execute("""
                    SELECT user_id, exchange_name, api_key, secret_key, passphrase, is_active
                    FROM user_exchange_keys
                    WHERE api_key IS NOT NULL AND api_key != ''
                """)
                
                restored_count = 0
                for user_id, exchange, api_key, secret_key, passphrase, is_active in cursor.fetchall():
                    try:
                        # Вставляем в основную БД (ключи уже зашифрованы)
                        main_cursor.execute("""
                            INSERT OR REPLACE INTO user_exchange_keys
                            (user_id, exchange_name, api_key, secret_key, passphrase, is_active, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (user_id, exchange, api_key, secret_key, passphrase, is_active))
                        
                        restored_count += 1
                        print(f"      ✅ Восстановлены ключи для пользователя {user_id}, биржа {exchange}")
                    except Exception as e:
                        print(f"      ❌ Ошибка восстановления для {user_id}: {e}")
                
                main_conn.commit()
                main_conn.close()
                
                if restored_count > 0:
                    print(f"\n✅ Успешно восстановлено {restored_count} записей с ключами!")
                    conn.close()
                    return True
                
            else:
                print("   ❌ Ключи не найдены")
            
            conn.close()
            
        except Exception as e:
            print(f"   ❌ Ошибка проверки backup: {e}")
            continue
    
    print("\n❌ Ключи не найдены ни в одном backup файле")
    return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 ВОССТАНОВЛЕНИЕ КЛЮЧЕЙ ИЗ BACKUP БД")
    print("=" * 60)
    print()
    
    success = restore_keys_from_backup()
    
    if success:
        print("\n✅ Ключи восстановлены! Теперь можно установить режим 'auto'.")
        print("   Запустите: python3 scripts/set_auto_mode_for_users_with_keys.py")
    
    sys.exit(0 if success else 1)

