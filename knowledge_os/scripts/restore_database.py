#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт восстановления поврежденной базы данных
Команда: Роман (Database Engineer), Сергей (DevOps Engineer)
"""

import os
import sys
import sqlite3
import shutil
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Путь к базе данных
DB_PATH = os.getenv("DATABASE", "trading.db")
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)


def create_backup(db_path: str) -> str:
    """Создает резервную копию базы данных"""
    logger.info(f"📦 Создание бэкапа базы данных: {db_path}")
    
    if not os.path.exists(db_path):
        logger.warning(f"⚠️ База данных не найдена: {db_path}")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"trading_db_backup_{timestamp}.db"
    
    try:
        # Пытаемся использовать SQLite backup API
        source_uri = f"file:{os.path.abspath(db_path)}?mode=ro"
        with sqlite3.connect(source_uri, uri=True) as src_conn:
            with sqlite3.connect(str(backup_path)) as dst_conn:
                src_conn.backup(dst_conn)
        logger.info(f"✅ Бэкап создан: {backup_path}")
        return str(backup_path)
    except sqlite3.Error as e:
        logger.warning(f"⚠️ Ошибка SQLite backup API: {e}, используем прямое копирование")
        try:
            shutil.copy2(db_path, backup_path)
            logger.info(f"✅ Бэкап создан (прямое копирование): {backup_path}")
            return str(backup_path)
        except Exception as e2:
            logger.error(f"❌ Ошибка создания бэкапа: {e2}")
            return None


def check_database_integrity(db_path: str) -> bool:
    """Проверяет целостность базы данных"""
    logger.info(f"🔍 Проверка целостности базы данных: {db_path}")
    
    if not os.path.exists(db_path):
        logger.warning(f"⚠️ База данных не найдена: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем целостность
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        conn.close()
        
        if result and result[0] == "ok":
            logger.info("✅ База данных целостна")
            return True
        else:
            logger.error(f"❌ База данных повреждена: {result}")
            return False
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка проверки целостности: {e}")
        return False


def recover_database(db_path: str) -> bool:
    """Пытается восстановить базу данных через .recover"""
    logger.info(f"🔧 Попытка восстановления базы данных: {db_path}")
    
    if not os.path.exists(db_path):
        logger.warning(f"⚠️ База данных не найдена: {db_path}")
        return False
    
    recovered_path = db_path + ".recovered"
    
    try:
        conn = sqlite3.connect(db_path)
        recovered_conn = sqlite3.connect(recovered_path)
        
        # Пытаемся восстановить
        conn.backup(recovered_conn)
        
        conn.close()
        recovered_conn.close()
        
        # Проверяем восстановленную БД
        if check_database_integrity(recovered_path):
            logger.info(f"✅ База данных восстановлена: {recovered_path}")
            # Заменяем оригинальную БД
            shutil.move(recovered_path, db_path)
            logger.info(f"✅ Восстановленная БД заменяет оригинальную")
            return True
        else:
            logger.error(f"❌ Восстановленная БД также повреждена")
            os.remove(recovered_path)
            return False
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка восстановления: {e}")
        if os.path.exists(recovered_path):
            os.remove(recovered_path)
        return False


def recreate_database_structure(db_path: str, schema_file: str = "database_schema.sql") -> bool:
    """Пересоздает структуру базы данных из схемы"""
    logger.info(f"🔨 Пересоздание структуры базы данных: {db_path}")
    
    # Удаляем поврежденную БД
    if os.path.exists(db_path):
        logger.info(f"🗑️ Удаление поврежденной БД: {db_path}")
        os.remove(db_path)
    
    # Создаем новую БД
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Читаем схему
        if os.path.exists(schema_file):
            logger.info(f"📖 Чтение схемы из: {schema_file}")
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # Выполняем SQL из схемы
            cursor.executescript(schema_sql)
            conn.commit()
            logger.info("✅ Структура базы данных создана")
        else:
            logger.warning(f"⚠️ Файл схемы не найден: {schema_file}, создаем базовую структуру")
            # Создаем базовую структуру
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    tp1 REAL NOT NULL,
                    tp2 REAL NOT NULL,
                    sl REAL NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    username TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("✅ Базовая структура создана")
        
        conn.close()
        
        # Проверяем целостность новой БД
        if check_database_integrity(db_path):
            logger.info("✅ Новая база данных создана и проверена")
            return True
        else:
            logger.error("❌ Новая база данных повреждена")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка создания структуры: {e}")
        return False


def main():
    """Основная функция восстановления"""
    logger.info("=" * 80)
    logger.info("🔧 ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ ATRA")
    logger.info("=" * 80)
    logger.info(f"База данных: {DB_PATH}")
    logger.info("")
    
    # Шаг 1: Проверка существования БД
    if not os.path.exists(DB_PATH):
        logger.warning(f"⚠️ База данных не найдена: {DB_PATH}")
        logger.info("📝 Создаем новую базу данных...")
        if recreate_database_structure(DB_PATH):
            logger.info("✅ Новая база данных создана успешно")
            return 0
        else:
            logger.error("❌ Ошибка создания новой базы данных")
            return 1
    
    # Шаг 2: Проверка целостности
    if check_database_integrity(DB_PATH):
        logger.info("✅ База данных целостна, восстановление не требуется")
        return 0
    
    # Шаг 3: Создание бэкапа
    backup_path = create_backup(DB_PATH)
    if not backup_path:
        logger.error("❌ Не удалось создать бэкап, прерываем операцию")
        return 1
    
    # Шаг 4: Попытка восстановления
    logger.info("")
    logger.info("🔧 Попытка восстановления через .recover...")
    if recover_database(DB_PATH):
        logger.info("✅ База данных восстановлена успешно")
        return 0
    
    # Шаг 5: Пересоздание структуры
    logger.info("")
    logger.info("🔨 Пересоздание структуры базы данных...")
    if recreate_database_structure(DB_PATH):
        logger.info("✅ Структура базы данных пересоздана успешно")
        logger.warning("⚠️ ВНИМАНИЕ: Все данные потеряны! Бэкап сохранен в: " + backup_path)
        return 0
    else:
        logger.error("❌ Ошибка пересоздания структуры")
        return 1


if __name__ == "__main__":
    sys.exit(main())

