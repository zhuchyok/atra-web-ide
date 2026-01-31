#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autonomous Janitor - Система автоматической очистки мусора
Автор: Сергей (DevOps) + Виктория (Lead)
"""

import os
import shutil
import logging
import asyncio
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
        self.min_free_gb = 8.0 # Минимум 8 ГБ свободно (было 5)
        self.log_max_age_days = 3 # Логи храним 3 дня (было 7)
        self.backup_max_age_days = 2 # Бекапы храним 2 дня (было 3)
        self.max_backup_count = 15 # Лимит на количество файлов бекапа
        self.max_log_size_mb = 50 # Максимальный размер лог-файла перед обрезкой
        self.max_rotated_logs = 3 # Максимум rotated логов (system.log.1, system.log.2, system.log.3)
        self.max_ai_learning_backups = 5 # Максимум бэкапов в ai_learning_data
        
    async def run_cleanup_loop(self):
        """Цикл очистки раз в 1 час (было 6)"""
        logger.info("🧹 [JANITOR] Система авто-очистки запущена (интервал: 1 час)")
        while True:
            try:
                self.perform_cleanup()
            except Exception as e:
                logger.error("❌ [JANITOR] Ошибка при очистке: %s", e)
            
            await asyncio.sleep(3600) # 1 час (было 21600)

    def perform_cleanup(self):
        """Основная логика очистки"""
        try:
            total, used, free = shutil.disk_usage(self.base_path)
            free_gb = free / (1024**3)
            
            logger.info("📊 [JANITOR] Статус диска: Свободно %.2f ГБ из %.2f ГБ", free_gb, total / (1024**3))
            
            # 1. Профилактическая очистка по количеству бекапов
            self._rotate_backups_by_count()
            
            # 2. Очистка rotated логов (всегда)
            self._clean_rotated_logs()
            
            # 3. Очистка ai_learning_data бэкапов (всегда)
            self._clean_ai_learning_backups()
            
            # 4. Экстренная очистка по свободному месту
            if free_gb < self.min_free_gb:
                logger.warning("⚠️ [JANITOR] Мало места (%.2f ГБ). Запуск глубокой очистки...", free_gb)
                self._clean_backups()
                self._clean_old_logs()
                self._clean_large_logs()
                self._clean_pycache()
                self._clean_git_objects()
                
                # Повторная проверка
                _, _, new_free = shutil.disk_usage(self.base_path)
                logger.info("✅ [JANITOR] Очистка завершена. Теперь свободно %.2f ГБ", new_free / (1024**3))
            else:
                # Очистка старых логов даже если места достаточно
                self._clean_old_logs()
                self._clean_large_logs()
                logger.info("✅ [JANITOR] Профилактика завершена.")
        except Exception as e:
            logger.error("❌ [JANITOR] Критическая ошибка в perform_cleanup: %s", e)

    def _rotate_backups_by_count(self):
        """Ограничивает количество бекапов в папке"""
        backup_path = os.path.join(self.base_path, "backups")
        if os.path.exists(backup_path):
            files = [os.path.join(backup_path, f) for f in os.listdir(backup_path) if os.path.isfile(os.path.join(backup_path, f))]
            if len(files) > self.max_backup_count:
                files.sort(key=os.path.getmtime)
                to_delete = files[:-self.max_backup_count]
                for f in to_delete:
                    try:
                        os.remove(f)
                        logger.info("🗑️ [JANITOR] Удален лишний бекап: %s", os.path.basename(f))
                    except: pass

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
        cleaned = 0
        for root, _, files in os.walk(self.base_path):
            for file in files:
                # Пропускаем rotated логи (их обрабатывает _clean_rotated_logs)
                if ".log." in file and file.split(".log.")[-1].isdigit():
                    continue
                    
                if file.endswith(".log"):
                    file_path = os.path.join(root, file)
                    try:
                        file_age = now - datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_age.days > self.log_max_age_days:
                            os.remove(file_path)
                            cleaned += 1
                            logger.info("🗑️ [JANITOR] Удален старый лог: %s", file)
                    except Exception:
                        pass
        if cleaned > 0:
            logger.info("✅ [JANITOR] Удалено старых логов: %d", cleaned)

    def _clean_rotated_logs(self):
        """Удаляет лишние rotated логи (оставляет только последние N)"""
        import glob
        cleaned = 0
        
        # Ищем все rotated логи в папке logs
        logs_dir = os.path.join(self.base_path, "logs")
        if os.path.exists(logs_dir):
            # Группируем по базовому имени (system.log, errors.log и т.д.)
            rotated_patterns = {}
            for log_file in glob.glob(os.path.join(logs_dir, "*.log.*")):
                try:
                    # Извлекаем базовое имя и номер (system.log.1 -> system.log, 1)
                    parts = os.path.basename(log_file).rsplit(".", 2)
                    if len(parts) == 3 and parts[-1].isdigit():
                        base_name = f"{parts[0]}.{parts[1]}"
                        if base_name not in rotated_patterns:
                            rotated_patterns[base_name] = []
                        rotated_patterns[base_name].append((int(parts[-1]), log_file))
                except Exception:
                    pass
            
            # Для каждого базового имени оставляем только последние N файлов
            for base_name, files in rotated_patterns.items():
                files.sort(key=lambda x: x[0], reverse=True)  # Сортируем по номеру (больше = новее)
                if len(files) > self.max_rotated_logs:
                    to_delete = files[self.max_rotated_logs:]
                    for _, file_path in to_delete:
                        try:
                            os.remove(file_path)
                            cleaned += 1
                            logger.info("🗑️ [JANITOR] Удален rotated лог: %s", os.path.basename(file_path))
                        except Exception:
                            pass
        
        if cleaned > 0:
            logger.info("✅ [JANITOR] Удалено rotated логов: %d", cleaned)

    def _clean_large_logs(self):
        """Обрезает или удаляет слишком большие лог-файлы"""
        cleaned = 0
        truncated = 0
        
        for root, _, files in os.walk(self.base_path):
            for file in files:
                if file.endswith(".log") and ".log." not in file:  # Только основные логи, не rotated
                    file_path = os.path.join(root, file)
                    try:
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        if file_size_mb > self.max_log_size_mb:
                            # Обрезаем до последних 1000 строк
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    lines = f.readlines()
                                
                                if len(lines) > 1000:
                                    with open(file_path, 'w', encoding='utf-8') as f:
                                        f.write(f"--- Log truncated by Janitor at {get_utc_now()} ---\n")
                                        f.write(f"--- Previous size: {file_size_mb:.1f} MB, kept last 1000 lines ---\n")
                                        f.writelines(lines[-1000:])
                                    truncated += 1
                                    logger.info("✂️ [JANITOR] Обрезан большой лог: %s (было %.1f MB)", 
                                              os.path.basename(file_path), file_size_mb)
                            except Exception:
                                # Если не получилось обрезать, удаляем
                                os.remove(file_path)
                                cleaned += 1
                                logger.info("🗑️ [JANITOR] Удален слишком большой лог: %s (%.1f MB)", 
                                          os.path.basename(file_path), file_size_mb)
                    except Exception:
                        pass
        
        if cleaned > 0 or truncated > 0:
            logger.info("✅ [JANITOR] Обработано больших логов: удалено %d, обрезано %d", cleaned, truncated)

    def _clean_ai_learning_backups(self):
        """Очищает старые бэкапы в ai_learning_data"""
        ai_learning_dir = os.path.join(self.base_path, "ai_learning_data")
        if not os.path.exists(ai_learning_dir):
            return
        
        import glob
        cleaned = 0
        
        # Ищем все backup файлы
        backup_files = glob.glob(os.path.join(ai_learning_dir, "*.backup_*"))
        
        if len(backup_files) > self.max_ai_learning_backups:
            # Сортируем по времени модификации (новые первыми)
            backup_files.sort(key=os.path.getmtime, reverse=True)
            to_delete = backup_files[self.max_ai_learning_backups:]
            
            for file_path in to_delete:
                try:
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    os.remove(file_path)
                    cleaned += 1
                    logger.info("🗑️ [JANITOR] Удален старый бэкап ai_learning: %s (%.1f MB)", 
                              os.path.basename(file_path), file_size_mb)
                except Exception:
                    pass
        
        if cleaned > 0:
            logger.info("✅ [JANITOR] Удалено бэкапов ai_learning: %d", cleaned)

    def _clean_git_objects(self):
        """Очищает старые git объекты (gc)"""
        git_dir = os.path.join(self.base_path, ".git")
        if os.path.exists(git_dir):
            try:
                import subprocess
                # Запускаем git gc для очистки
                result = subprocess.run(
                    ["git", "-C", self.base_path, "gc", "--prune=now", "--aggressive"],
                    capture_output=True,
                    timeout=300,  # 5 минут максимум
                    cwd=self.base_path
                )
                if result.returncode == 0:
                    logger.info("🧹 [JANITOR] Git объекты очищены")
                else:
                    logger.debug("⚠️ [JANITOR] Git gc завершился с кодом %d", result.returncode)
            except Exception as e:
                logger.debug("⚠️ [JANITOR] Не удалось очистить git объекты: %s", e)

    def _clean_pycache(self):
        """Удаляет __pycache__ для освобождения inodes и места"""
        for root, dirs, _ in os.walk(self.base_path):
            for d in dirs:
                if d == "__pycache__":
                    shutil.rmtree(os.path.join(root, d))

async def start_janitor_loop():
    janitor = AutonomousJanitor()
    await janitor.run_cleanup_loop()

