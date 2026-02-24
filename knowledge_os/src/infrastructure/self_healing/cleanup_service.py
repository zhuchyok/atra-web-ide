"""
🧹 AUTONOMOUS JANITOR SYSTEM
Система автоматической очистки старых данных, логов и оптимизации БД.
Автор: Сергей (DevOps) + Игорь (Backend)
"""

import glob
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class CleanupService:
    def __init__(self, db_path: str = "trading.db", base_dir: str = "/root/atra"):
        self.db_path = db_path
        self.base_dir = base_dir

        # Настройки хранения (Retention Policy)
        self.RETENTION_LOGS_DAYS = 3
        self.RETENTION_DB_LOGS_DAYS = 14
        self.RETENTION_RESEARCH_DAYS = 7
        self.MAX_LOG_SIZE_MB = 50

    async def run_full_cleanup(self):
        """Запуск полного цикла очистки"""
        logger.info("🧹 [JANITOR] Запуск цикла полной очистки системы...")
        start_time = time.time()

        try:
            # 1. Очистка файлов логов
            self._cleanup_log_files()

            # 2. Очистка базы данных
            self._cleanup_database()

            # 3. Очистка папок с исследованиями
            self._cleanup_research_data()

            # 4. Системная очистка (journalctl)
            self._cleanup_system_journals()

            duration = time.time() - start_time
            logger.info(f"✅ [JANITOR] Очистка завершена за {duration:.2f} сек.")

        except Exception as e:
            logger.error(f"❌ [JANITOR] Критическая ошибка при очистке: {e}")

    def _cleanup_log_files(self):
        """Удаляет старые или слишком большие лог-файлы"""
        logger.info("🔍 [JANITOR] Проверка лог-файлов...")
        log_files = glob.glob(os.path.join(self.base_dir, "*.log"))
        log_files.extend(glob.glob(os.path.join(self.base_dir, "logs", "*.log")))

        now = time.time()
        for f in log_files:
            try:
                # По времени
                if os.stat(f).st_mtime < now - (self.RETENTION_LOGS_DAYS * 86400):
                    os.remove(f)
                    logger.info(f"🗑️ Удален старый лог: {os.path.basename(f)}")
                    continue

                # По размеру (если > MAX_LOG_SIZE_MB, обнуляем)
                if os.path.getsize(f) > self.MAX_LOG_SIZE_MB * 1024 * 1024:
                    with open(f, "w") as log_file:
                        log_file.write(f"--- Log truncated by Janitor at {get_utc_now()} ---\n")
                    logger.info(f"✂️ Обрезан слишком большой лог: {os.path.basename(f)}")
            except Exception as e:
                logger.error(f"Ошибка при очистке лога {f}: {e}")

    def _cleanup_database(self):
        """Удаляет старые записи из БД и делает VACUUM"""
        logger.info("🔍 [JANITOR] Очистка базы данных...")
        if not os.path.exists(self.db_path):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Лимит времени
            limit_db = (get_utc_now() - timedelta(days=self.RETENTION_DB_LOGS_DAYS)).isoformat()

            # Очистка signals_log (старые сигналы)
            cursor.execute("DELETE FROM signals_log WHERE created_at < ?", (limit_db,))
            deleted_signals = cursor.rowcount

            # Очистка order_audit_log (старый аудит)
            cursor.execute("DELETE FROM order_audit_log WHERE created_at < ?", (limit_db,))
            deleted_orders = cursor.rowcount

            # Очистка key_operations_log
            cursor.execute("DELETE FROM key_operations_log WHERE created_at < ?", (limit_db,))

            # Сохраняем и сжимаем
            conn.commit()
            logger.info(
                f"🗑️ БД: Удалено {deleted_signals} старых сигналов и {deleted_orders} логов ордеров."
            )

            logger.info("⚙️ [JANITOR] Запуск VACUUM (сжатие БД)...")
            cursor.execute("VACUUM")
            conn.close()

        except Exception as e:
            logger.error(f"Ошибка при очистке БД: {e}")

    def _cleanup_research_data(self):
        """Удаляет старые гипотезы и ИИ-кэши"""
        research_dir = os.path.join(self.base_dir, "research")
        if not os.path.exists(research_dir):
            return

        now = time.time()
        for f in glob.glob(os.path.join(research_dir, "*")):
            try:
                if os.stat(f).st_mtime < now - (self.RETENTION_RESEARCH_DAYS * 86400):
                    if os.path.isfile(f):
                        os.remove(f)
                        logger.info(f"🗑️ Удален старый файл исследования: {os.path.basename(f)}")
            except Exception as e:
                logger.error(f"Ошибка при очистке папки research: {e}")

    def _cleanup_system_journals(self):
        """Очистка системных логов journalctl (через shell)"""
        try:
            os.system("journalctl --vacuum-time=3d > /dev/null 2>&1")
            logger.info("🧹 Системные журналы очищены (retention: 3d)")
        except Exception:
            pass


async def start_janitor_loop():
    """Фоновая задача для ежедневной очистки"""
    janitor = CleanupService()
    while True:
        await janitor.run_full_cleanup()
        # Спим 24 часа
        await asyncio.sleep(86400)
