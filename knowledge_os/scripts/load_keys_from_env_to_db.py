#!/usr/bin/env python3
"""
Скрипт для загрузки ключей Bitget из env файлов в БД
"""

import os
import sys
import sqlite3
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_keys_from_env():
    """Загружает ключи из env файлов и сохраняет в БД"""
    
    # Путь к БД
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'trading.db')
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return False
    
    # Читаем ключи из env файлов
    api_key = None
    secret_key = None
    passphrase = None
    
    # Проверяем .env файл
    env_file = Path('.env')
    if env_file.exists():
        print("✅ Найден файл .env")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('BITGET_API_KEY=') and not line.startswith('#'):
                    api_key = line.split('=', 1)[1].strip()
                elif line.startswith('BITGET_SECRET_KEY=') and not line.startswith('#'):
                    secret_key = line.split('=', 1)[1].strip()
                elif line.startswith('BITGET_PASSPHRASE=') and not line.startswith('#'):
                    passphrase = line.split('=', 1)[1].strip()
    
    # Если не нашли в .env, проверяем env
    if not api_key:
        env_file = Path('env')
        if env_file.exists():
            print("✅ Найден файл env")
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('BITGET_API_KEY=') and not line.startswith('#') and not api_key:
                        api_key = line.split('=', 1)[1].strip()
                    elif line.startswith('BITGET_SECRET_KEY=') and not line.startswith('#') and not secret_key:
                        secret_key = line.split('=', 1)[1].strip()
                    elif line.startswith('BITGET_PASSPHRASE=') and not line.startswith('#') and not passphrase:
                        passphrase = line.split('=', 1)[1].strip()
    
    # Проверяем переменные окружения
    if not api_key:
        api_key = os.getenv('BITGET_API_KEY')
    if not secret_key:
        secret_key = os.getenv('BITGET_SECRET_KEY')
    if not passphrase:
        passphrase = os.getenv('BITGET_PASSPHRASE')
    
    if not api_key or not secret_key:
        print("❌ Ключи Bitget не найдены в env файлах или переменных окружения")
        print("   Проверьте файлы .env или env на наличие:")
        print("   BITGET_API_KEY=...")
        print("   BITGET_SECRET_KEY=...")
        print("   BITGET_PASSPHRASE=...")
        return False
    
    print(f"✅ Найдены ключи:")
    print(f"   API Key: {api_key[:10]}...{api_key[-5:] if len(api_key) > 15 else ''}")
    print(f"   Secret Key: {'*' * 20}")
    print(f"   Passphrase: {passphrase if passphrase else 'не указан'}")
    
    # Сохраняем в БД для обоих пользователей
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем наличие таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_exchange_keys'
        """)
        if not cursor.fetchone():
            print("❌ Таблица user_exchange_keys не найдена")
            return False
        
        # Импортируем функцию шифрования
        try:
            from src.database.acceptance import AcceptanceDatabase
            adb = AcceptanceDatabase()
        except ImportError:
            print("❌ Не удалось импортировать AcceptanceDatabase")
            return False
        
        # Сохраняем ключи для обоих пользователей
        users = [556251171, 958930260]
        success_count = 0
        
        for user_id in users:
            # Используем async функцию через синхронный вызов
            import asyncio
            try:
                result = asyncio.run(adb.save_exchange_keys(user_id, 'bitget', api_key, secret_key, passphrase))
                if result:
                    print(f"✅ Ключи сохранены для пользователя {user_id}")
                    success_count += 1
                else:
                    print(f"❌ Не удалось сохранить ключи для пользователя {user_id}")
            except Exception as e:
                print(f"❌ Ошибка сохранения ключей для {user_id}: {e}")
        
        conn.close()
        
        if success_count > 0:
            print(f"\n✅ Ключи успешно сохранены для {success_count} пользователей")
            return True
        else:
            print("\n❌ Не удалось сохранить ключи ни для одного пользователя")
            return False
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 ЗАГРУЗКА КЛЮЧЕЙ BITGET ИЗ ENV В БД")
    print("=" * 60)
    print()
    
    success = load_keys_from_env()
    
    sys.exit(0 if success else 1)

