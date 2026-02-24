"""
Мониторинг и автоматическое восстановление БД
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime
from typing import Optional, Tuple

from config import DATABASE
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)

BACKUP_DIR = "backups"


def check_db_integrity(db_path: str = DATABASE) -> Tuple[bool, str]:
    """
    Проверяет целостность БД

    Returns:
        (is_ok, message)
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()

        # Проверка целостности
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()

        conn.close()

        if result and result[0] == "ok":
            return True, "✅ БД в порядке"
        else:
            return False, f"❌ БД повреждена: {result}"

    except sqlite3.DatabaseError as e:
        return False, f"❌ Ошибка БД: {e}"
    except Exception as e:
        return False, f"❌ Неизвестная ошибка: {e}"


def create_emergency_backup(db_path: str = DATABASE) -> Optional[str]:
    """
    Создает экстренный бэкап БД

    Returns:
        Путь к бэкапу или None
    """
    try:
        if not os.path.exists(db_path):
            logger.error("БД не существует: %s", db_path)
            return None

        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"emergency_{os.path.basename(db_path)}_{timestamp}")

        shutil.copy2(db_path, backup_path)
        logger.info("🆘 Экстренный бэкап создан: %s", backup_path)
        return backup_path

    except Exception as e:
        logger.error("Не удалось создать экстренный бэкап: %s", e)
        return None


def find_latest_backup(db_name: str = "trading.db") -> Optional[str]:
    """
    Находит самый свежий бэкап

    Returns:
        Путь к бэкапу или None
    """
    try:
        if not os.path.exists(BACKUP_DIR):
            return None

        backups = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.startswith(db_name) or filename.startswith(f"emergency_{db_name}"):
                path = os.path.join(BACKUP_DIR, filename)
                if os.path.isfile(path):
                    mtime = os.path.getmtime(path)
                    backups.append((mtime, path))

        if not backups:
            return None

        # Сортируем по времени, берем самый свежий
        backups.sort(reverse=True)
        return backups[0][1]

    except Exception as e:
        logger.error("Ошибка поиска бэкапа: %s", e)
        return None


def restore_from_backup(backup_path: str, db_path: str = DATABASE) -> bool:
    """
    Восстанавливает БД из бэкапа

    Returns:
        True если успешно
    """
    try:
        if not os.path.exists(backup_path):
            logger.error("Бэкап не найден: %s", backup_path)
            return False

        # Проверяем целостность бэкапа
        is_ok, msg = check_db_integrity(backup_path)
        if not is_ok:
            logger.error("Бэкап поврежден: %s", msg)
            return False

        # Создаем экстренный бэкап текущей (поврежденной) БД
        if os.path.exists(db_path):
            corrupted_backup = os.path.join(
                BACKUP_DIR,
                f"corrupted_{os.path.basename(db_path)}_{get_utc_now().strftime('%Y%m%d_%H%M%S')}",
            )
            shutil.copy2(db_path, corrupted_backup)
            logger.info("💾 Поврежденная БД сохранена: %s", corrupted_backup)

        # Восстанавливаем из бэкапа
        shutil.copy2(backup_path, db_path)
        logger.info("✅ БД восстановлена из бэкапа: %s", backup_path)

        # Удаляем WAL и SHM файлы
        for ext in ["-wal", "-shm"]:
            wal_file = db_path + ext
            if os.path.exists(wal_file):
                os.remove(wal_file)
                logger.info("🗑️ Удален файл: %s", wal_file)

        return True

    except Exception as e:
        logger.error("Ошибка восстановления БД: %s", e)
        return False


def auto_fix_database(db_path: str = DATABASE) -> bool:
    """
    Автоматически исправляет БД

    Returns:
        True если БД исправлена или в порядке
    """
    logger.info("🔧 Запуск автоматического исправления БД...")

    # 1. Проверяем целостность
    is_ok, msg = check_db_integrity(db_path)
    logger.info(msg)

    if is_ok:
        return True

    # 2. БД повреждена - создаем экстренный бэкап
    logger.warning("⚠️ БД повреждена! Начинаем восстановление...")
    create_emergency_backup(db_path)

    # 3. Ищем последний рабочий бэкап
    backup_path = find_latest_backup()
    if not backup_path:
        logger.error("❌ Не найден рабочий бэкап!")
        return False

    logger.info("📂 Найден бэкап: %s", backup_path)

    # 4. Восстанавливаем
    success = restore_from_backup(backup_path, db_path)

    if success:
        # 5. Проверяем восстановленную БД
        is_ok, msg = check_db_integrity(db_path)
        logger.info(msg)
        return is_ok

    return False


def checkpoint_wal(db_path: str = DATABASE) -> bool:
    """
    Принудительно синхронизирует WAL в основную БД

    Returns:
        True если успешно
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()

        # Checkpoint WAL
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        result = cursor.fetchone()

        conn.close()

        logger.info("✅ WAL checkpoint: %s", result)
        return True

    except Exception as e:
        logger.error("Ошибка WAL checkpoint: %s", e)
        return False


def optimize_database(db_path: str = DATABASE) -> bool:
    """
    Оптимизирует БД (VACUUM)

    Returns:
        True если успешно
    """
    try:
        conn = sqlite3.connect(db_path, timeout=60.0)

        # VACUUM не работает в транзакциях
        conn.isolation_level = None
        cursor = conn.cursor()

        logger.info("🔄 Запуск VACUUM...")
        cursor.execute("VACUUM;")

        logger.info("✅ VACUUM завершен")
        conn.close()
        return True

    except Exception as e:
        logger.error("Ошибка VACUUM: %s", e)
        return False


def get_db_health_status(db_path: str = DATABASE) -> dict:
    """
    Получает полный статус здоровья БД

    Returns:
        Словарь со статусом
    """
    status = {
        "path": db_path,
        "exists": os.path.exists(db_path),
        "size_mb": 0,
        "integrity_ok": False,
        "integrity_message": "",
        "wal_exists": False,
        "wal_size_mb": 0,
        "shm_exists": False,
        "backup_count": 0,
        "latest_backup": None,
    }

    try:
        if status["exists"]:
            status["size_mb"] = round(os.path.getsize(db_path) / 1024 / 1024, 2)

        # Проверка целостности
        is_ok, msg = check_db_integrity(db_path)
        status["integrity_ok"] = is_ok
        status["integrity_message"] = msg

        # WAL файлы
        wal_path = db_path + "-wal"
        if os.path.exists(wal_path):
            status["wal_exists"] = True
            status["wal_size_mb"] = round(os.path.getsize(wal_path) / 1024 / 1024, 2)

        shm_path = db_path + "-shm"
        status["shm_exists"] = os.path.exists(shm_path)

        # Бэкапы
        if os.path.exists(BACKUP_DIR):
            backups = [f for f in os.listdir(BACKUP_DIR) if "trading.db" in f]
            status["backup_count"] = len(backups)

            latest = find_latest_backup()
            if latest:
                status["latest_backup"] = latest

    except Exception as e:
        logger.error("Ошибка получения статуса БД: %s", e)

    return status


if __name__ == "__main__":
    # Тест системы
    logging.basicConfig(level=logging.INFO)

    print("🔍 Проверка БД...")
    health = get_db_health_status()

    print("\n📊 Статус БД:")
    for key, value in health.items():
        print(f"  {key}: {value}")

    if not health["integrity_ok"]:
        print("\n🔧 Запуск автоматического исправления...")
        auto_fix_database()
    else:
        print("\n✅ БД в порядке!")
