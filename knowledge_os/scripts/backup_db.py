#!/usr/bin/env python3
"""
💾 СКРИПТ АВТОМАТИЧЕСКОГО БЭКАПА БД ATRA
Производит ротацию и сохранение базы данных trading.db
"""

import os
import sqlite3
import shutil
import logging
from datetime import datetime, timedelta

from src.shared.utils.datetime_utils import get_utc_now

# Настройки
BASE_DIR = "/root/atra"
DB_PATH = os.path.join(BASE_DIR, "trading.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups/db")
MAX_BACKUPS = 7  # Храним за последние 7 дней

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_backup():
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR, exist_ok=True)

        # Имя файла с меткой времени
        timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"trading_backup_{timestamp}.db")

        logger.info("📦 Начало бэкапа базы данных...")
        
        # Безопасное копирование SQLite через API (не блокирует БД)
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()

        # Архивируем для экономии места
        import subprocess
        subprocess.run(["gzip", backup_path], check=True)
        logger.info("✅ Бэкап успешно создан и сжат: %s.gz", backup_path)

        # Ротация (удаление старых)
        clean_old_backups()

    except Exception as e:
        logger.error("❌ Ошибка при создании бэкапа: %s", e)

def clean_old_backups():
    """Удаляет файлы старше MAX_BACKUPS штук"""
    try:
        files = [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".gz")]
        files.sort(key=os.path.getmtime, reverse=True)

        if len(files) > MAX_BACKUPS:
            for old_file in files[MAX_BACKUPS:]:
                os.remove(old_file)
                logger.info("🗑️ Удален старый бэкап: %s", old_file)
    except Exception as e:
        logger.error("❌ Ошибка при ротации бэкапов: %s", e)

if __name__ == "__main__":
    run_backup()

