#!/usr/bin/env python3
"""
Autonomous Janitor - Система автоматической очистки мусора
Автор: Сергей (DevOps) + Виктория (Lead)
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class AutonomousJanitor:
    """
    Отвечает за поддержание свободного места на диске.
    Удаляет старые логи, бэкапы и временные файлы.
    """

    def __init__(self, base_path: str = "/root/atra"):
        self.base_path = base_path
        self.min_free_gb = 8.0  # Минимум 8 ГБ свободно (было 5)
        self.log_max_age_days = 3  # Логи храним 3 дня (было 7)
        self.backup_max_age_days = 2  # Бекапы храним 2 дня (было 3)
        self.max_backup_count = 15  # Лимит на количество файлов бекапа

    async def run_cleanup_loop(self):
        """Цикл очистки раз в 1 час (было 6)"""
        logger.info("🧹 [JANITOR] Система авто-очистки запущена (интервал: 1 час)")
        while True:
            try:
                self.perform_cleanup()
            except Exception as e:
                logger.error("❌ [JANITOR] Ошибка при очистке: %s", e)

            await asyncio.sleep(3600)  # 1 час (было 21600)

    def perform_cleanup(self):
        """Основная логика очистки"""
        try:
            total, used, free = shutil.disk_usage(self.base_path)
            free_gb = free / (1024**3)

            logger.info(
                "📊 [JANITOR] Статус диска: Свободно %.2f ГБ из %.2f ГБ", free_gb, total / (1024**3)
            )

            # 1. Профилактическая очистка по количеству бекапов
            self._rotate_backups_by_count()

            # 2. Экстренная очистка по свободному месту
            if free_gb < self.min_free_gb:
                logger.warning(
                    "⚠️ [JANITOR] Мало места (%.2f ГБ). Запуск глубокой очистки...", free_gb
                )
                self._clean_backups()
                self._clean_old_logs()
                self._clean_pycache()

                # Повторная проверка
                _, _, new_free = shutil.disk_usage(self.base_path)
                logger.info(
                    "✅ [JANITOR] Очистка завершена. Теперь свободно %.2f ГБ", new_free / (1024**3)
                )
            else:
                # Очистка старых логов даже если места достаточно
                self._clean_old_logs()
                logger.info("✅ [JANITOR] Профилактика завершена.")
        except Exception as e:
            logger.error("❌ [JANITOR] Критическая ошибка в perform_cleanup: %s", e)

    def _rotate_backups_by_count(self):
        """Ограничивает количество бекапов в папке"""
        backup_path = os.path.join(self.base_path, "backups")
        if os.path.exists(backup_path):
            files = [
                os.path.join(backup_path, f)
                for f in os.listdir(backup_path)
                if os.path.isfile(os.path.join(backup_path, f))
            ]
            if len(files) > self.max_backup_count:
                files.sort(key=os.path.getmtime)
                to_delete = files[: -self.max_backup_count]
                for f in to_delete:
                    try:
                        os.remove(f)
                        logger.info("🗑️ [JANITOR] Удален лишний бекап: %s", os.path.basename(f))
                    except:
                        pass

    def _clean_backups(self):
        """Удаляет старые бэкапы"""
        backup_path = os.path.join(self.base_path, "backups")
        if os.path.exists(backup_path):
            logger.info("🧹 [JANITOR] Очистка бэкапов...")
            shutil.rmtree(backup_path)
            os.makedirs(backup_path, exist_ok=True)

    def _clean_old_logs(self):
        """Удаляет логи старше N дней"""
        now = get_utc_now()
        for root, _, files in os.walk(self.base_path):
            for file in files:
                if file.endswith(".log") or ".log." in file:
                    file_path = os.path.join(root, file)
                    try:
                        file_age = now - datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_age.days > self.log_max_age_days:
                            os.remove(file_path)
                            logger.info("🗑️ [JANITOR] Удален старый лог: %s", file)
                    except Exception:
                        pass

    def _clean_pycache(self):
        """Удаляет __pycache__ для освобождения inodes и места"""
        for root, dirs, _ in os.walk(self.base_path):
            for d in dirs:
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(root, d))


async def start_janitor_loop():
    janitor = AutonomousJanitor()
    await janitor.run_cleanup_loop()
