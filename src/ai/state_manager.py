#!/usr/bin/env python3
"""
Менеджер состояния для AI-системы регулирования параметров
"""

import asyncio
import json
import logging
import os
import shutil
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class AIStateManager:
    """
    Менеджер состояния AI-системы с функциями:
    - Автоматическое сохранение состояния
    - Создание резервных копий
    - Восстановление после сбоев
    - Миграция данных между версиями
    """
    
    def __init__(self, 
                 base_dir: str = "ai_learning_data",
                 backup_interval_hours: int = 6,
                 max_backups: int = 10):
        self.base_dir = base_dir
        self.backup_interval_hours = backup_interval_hours
        self.max_backups = max_backups
        
        # Пути к файлам
        self.state_file = os.path.join(base_dir, "ai_regulator_state.json")
        self.pattern_file = os.path.join(base_dir, "pattern_effectiveness.json")
        self.backup_dir = os.path.join(base_dir, "backups")
        self.migration_log = os.path.join(base_dir, "migration_log.json")
        
        # Создаем директории
        self._ensure_directories()
        
        # Состояние автосохранения
        self.auto_save_enabled = True
        self.last_backup_time = 0.0
        self.save_queue = asyncio.Queue()
        
        # Запускаем фоновые задачи
        self._background_tasks: List[asyncio.Task] = []
        self._start_background_tasks_safe()
        
        logger.info("💾 AI State Manager инициализирован")
        logger.info("  📁 Базовая директория: %s", self.base_dir)
        logger.info("  🔄 Интервал резервирования: %d часов", self.backup_interval_hours)
    
    def _ensure_directories(self):
        """Создает необходимые директории"""
        directories = [
            self.base_dir,
            self.backup_dir,
            os.path.join(self.base_dir, "symbol_params"),
            os.path.join(self.base_dir, "exports"),
            os.path.join(self.base_dir, "logs")
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    async def start_background_tasks(self):
        """Запускает фоновые задачи"""
        if self._background_tasks:
            return  # Уже запущены
        
        # Задача автосохранения
        save_task = asyncio.create_task(self._auto_save_worker())
        self._background_tasks.append(save_task)
        
        # Задача создания резервных копий
        backup_task = asyncio.create_task(self._backup_worker())
        self._background_tasks.append(backup_task)
        
        # Задача очистки старых файлов
        cleanup_task = asyncio.create_task(self._cleanup_worker())
        self._background_tasks.append(cleanup_task)
        
        logger.info("🚀 Запущены фоновые задачи State Manager")
    
    def _start_background_tasks_safe(self):
        """Безопасный запуск фоновых задач с проверкой event loop"""
        try:
            # Проверяем, есть ли запущенный event loop
            loop = asyncio.get_running_loop()
            # Если есть, создаем задачи в текущем loop
            if self.auto_save_enabled:
                save_task = asyncio.create_task(self._auto_save_worker())
                self._background_tasks.append(save_task)
            
            backup_task = asyncio.create_task(self._backup_worker())
            self._background_tasks.append(backup_task)
            
            cleanup_task = asyncio.create_task(self._cleanup_worker())
            self._background_tasks.append(cleanup_task)
            
            logger.info("🔄 Фоновые задачи запущены в существующем event loop")
            
        except RuntimeError:
            # Нет запущенного event loop, запускаем в отдельном потоке
            import threading
            
            def run_background_tasks():
                try:
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    
                    if self.auto_save_enabled:
                        save_task = new_loop.create_task(self._auto_save_worker())
                        self._background_tasks.append(save_task)
                    
                    backup_task = new_loop.create_task(self._backup_worker())
                    self._background_tasks.append(backup_task)
                    
                    cleanup_task = new_loop.create_task(self._cleanup_worker())
                    self._background_tasks.append(cleanup_task)
                    
                    logger.info("🔄 Фоновые задачи запущены в новом event loop")
                    new_loop.run_forever()
                    
                except Exception as e:
                    logger.error("❌ Ошибка запуска фоновых задач: %s", e)
            
            thread = threading.Thread(target=run_background_tasks, daemon=True)
            thread.start()
            logger.info("🔄 Фоновые задачи запущены в отдельном потоке")
    
    async def stop_background_tasks(self):
        """Останавливает фоновые задачи"""
        for task in self._background_tasks:
            task.cancel()
        
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        
        self._background_tasks.clear()
        logger.info("🛑 Остановлены фоновые задачи State Manager")
    
    async def _auto_save_worker(self):
        """Фоновая задача автосохранения"""
        try:
            while True:
                # Ждем задачи сохранения из очереди
                save_data = await asyncio.wait_for(self.save_queue.get(), timeout=300)  # 5 минут таймаут
                
                try:
                    await self._perform_save(save_data)
                    self.save_queue.task_done()
                except Exception as e:
                    logger.error("❌ Ошибка автосохранения: %s", e)
        
        except asyncio.CancelledError:
            logger.debug("🛑 Auto-save worker остановлен")
        except Exception as e:
            logger.error("❌ Критическая ошибка в auto-save worker: %s", e)
    
    async def _backup_worker(self):
        """Фоновая задача создания резервных копий"""
        try:
            while True:
                await asyncio.sleep(3600)  # Проверяем каждый час
                
                current_time = time.time()
                time_since_backup = (current_time - self.last_backup_time) / 3600
                
                if time_since_backup >= self.backup_interval_hours:
                    await self.create_backup()
        
        except asyncio.CancelledError:
            logger.debug("🛑 Backup worker остановлен")
        except Exception as e:
            logger.error("❌ Критическая ошибка в backup worker: %s", e)
    
    async def _cleanup_worker(self):
        """Фоновая задача очистки старых файлов"""
        try:
            while True:
                await asyncio.sleep(24 * 3600)  # Проверяем раз в день
                await self.cleanup_old_files()
        
        except asyncio.CancelledError:
            logger.debug("🛑 Cleanup worker остановлен")
        except Exception as e:
            logger.error("❌ Критическая ошибка в cleanup worker: %s", e)
    
    async def save_state_async(self, 
                              regulator_state: Dict[str, Any],
                              pattern_data: Optional[Dict[str, Any]] = None,
                              priority: str = "normal"):
        """
        Асинхронное сохранение состояния
        
        Args:
            regulator_state: Состояние регулятора
            pattern_data: Данные паттернов (опционально)
            priority: Приоритет сохранения ("high", "normal", "low")
        """
        save_data = {
            "regulator_state": regulator_state,
            "pattern_data": pattern_data,
            "priority": priority,
            "timestamp": time.time()
        }
        
        # Добавляем в очередь сохранения
        await self.save_queue.put(save_data)
        
        logger.debug("💾 Добавлено в очередь сохранения (приоритет: %s)", priority)
    
    async def _perform_save(self, save_data: Dict[str, Any]):
        """Выполняет фактическое сохранение"""
        try:
            # Сохраняем состояние регулятора
            if save_data["regulator_state"]:
                await self._save_json_file(self.state_file, save_data["regulator_state"])
            
            # Сохраняем данные паттернов
            if save_data["pattern_data"]:
                await self._save_json_file(self.pattern_file, save_data["pattern_data"])
            
            logger.debug("✅ Состояние сохранено успешно")
        
        except Exception as e:
            logger.error("❌ Ошибка сохранения состояния: %s", e)
            raise
    
    async def _save_json_file(self, file_path: str, data: Dict[str, Any]):
        """Безопасное сохранение JSON файла"""
        temp_file = file_path + ".tmp"
        
        try:
            # Сохраняем во временный файл
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Атомарно перемещаем временный файл
            shutil.move(temp_file, file_path)
        
        except Exception as e:
            # Удаляем временный файл при ошибке
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise e
    
    async def load_state(self) -> Dict[str, Any]:
        """Загружает состояние системы"""
        state_data = {}
        
        try:
            # Загружаем состояние регулятора
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_data["regulator"] = json.load(f)
                logger.debug("📊 Загружено состояние регулятора")
            
            # Загружаем данные паттернов
            if os.path.exists(self.pattern_file):
                with open(self.pattern_file, 'r', encoding='utf-8') as f:
                    state_data["patterns"] = json.load(f)
                logger.debug("📊 Загружены данные паттернов")
            
            return state_data
        
        except Exception as e:
            logger.error("❌ Ошибка загрузки состояния: %s", e)
            
            # Пытаемся восстановить из резервной копии
            backup_state = await self.restore_from_backup()
            if backup_state:
                logger.info("✅ Состояние восстановлено из резервной копии")
                return backup_state
            
            return {}
    
    async def create_backup(self) -> bool:
        """Создает резервную копию текущего состояния"""
        try:
            timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
            backup_subdir = os.path.join(self.backup_dir, f"backup_{timestamp}")
            os.makedirs(backup_subdir, exist_ok=True)
            
            files_backed_up = 0
            
            # Копируем основные файлы состояния
            for source_file in [self.state_file, self.pattern_file]:
                if os.path.exists(source_file):
                    filename = os.path.basename(source_file)
                    backup_file = os.path.join(backup_subdir, filename)
                    shutil.copy2(source_file, backup_file)
                    files_backed_up += 1
            
            # Копируем параметры символов
            symbol_params_dir = os.path.join(self.base_dir, "symbol_params")
            if os.path.exists(symbol_params_dir):
                backup_symbol_dir = os.path.join(backup_subdir, "symbol_params")
                shutil.copytree(symbol_params_dir, backup_symbol_dir, dirs_exist_ok=True)
            
            # Создаем метаданные резервной копии
            metadata = {
                "timestamp": time.time(),
                "datetime": timestamp,
                "files_count": files_backed_up,
                "backup_size_mb": self._get_directory_size(backup_subdir) / (1024 * 1024)
            }
            
            metadata_file = os.path.join(backup_subdir, "backup_metadata.json")
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            self.last_backup_time = time.time()
            
            logger.info("💾 Создана резервная копия: %s (файлов: %d)", timestamp, files_backed_up)
            
            # Очищаем старые резервные копии
            await self._cleanup_old_backups()
            
            return True
        
        except Exception as e:
            logger.error("❌ Ошибка создания резервной копии: %s", e)
            return False
    
    async def restore_from_backup(self, backup_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Восстанавливает состояние из резервной копии
        
        Args:
            backup_name: Имя конкретной резервной копии или None для последней
        """
        try:
            if backup_name:
                backup_path = os.path.join(self.backup_dir, backup_name)
            else:
                # Находим последнюю резервную копию
                backup_path = await self._find_latest_backup()
            
            if not backup_path or not os.path.exists(backup_path):
                logger.warning("⚠️ Резервная копия не найдена")
                return None
            
            restored_state = {}
            
            # Восстанавливаем файлы состояния
            for filename in ["ai_regulator_state.json", "pattern_effectiveness.json"]:
                backup_file = os.path.join(backup_path, filename)
                if os.path.exists(backup_file):
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        if filename == "ai_regulator_state.json":
                            restored_state["regulator"] = json.load(f)
                        else:
                            restored_state["patterns"] = json.load(f)
            
            # Восстанавливаем параметры символов
            backup_symbol_dir = os.path.join(backup_path, "symbol_params")
            if os.path.exists(backup_symbol_dir):
                target_symbol_dir = os.path.join(self.base_dir, "symbol_params")
                if os.path.exists(target_symbol_dir):
                    shutil.rmtree(target_symbol_dir)
                shutil.copytree(backup_symbol_dir, target_symbol_dir)
            
            logger.info("✅ Состояние восстановлено из резервной копии: %s", os.path.basename(backup_path))
            return restored_state
        
        except Exception as e:
            logger.error("❌ Ошибка восстановления из резервной копии: %s", e)
            return None
    
    async def _find_latest_backup(self) -> Optional[str]:
        """Находит последнюю резервную копию"""
        try:
            if not os.path.exists(self.backup_dir):
                return None
            
            backup_dirs = []
            for item in os.listdir(self.backup_dir):
                backup_path = os.path.join(self.backup_dir, item)
                if os.path.isdir(backup_path) and item.startswith("backup_"):
                    metadata_file = os.path.join(backup_path, "backup_metadata.json")
                    if os.path.exists(metadata_file):
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        backup_dirs.append((metadata["timestamp"], backup_path))
            
            if backup_dirs:
                # Сортируем по времени создания и возвращаем последний
                backup_dirs.sort(key=lambda x: x[0], reverse=True)
                return backup_dirs[0][1]
            
            return None
        
        except Exception as e:
            logger.error("❌ Ошибка поиска резервных копий: %s", e)
            return None
    
    async def _cleanup_old_backups(self):
        """Очищает старые резервные копии"""
        try:
            if not os.path.exists(self.backup_dir):
                return
            
            backup_dirs = []
            for item in os.listdir(self.backup_dir):
                backup_path = os.path.join(self.backup_dir, item)
                if os.path.isdir(backup_path) and item.startswith("backup_"):
                    metadata_file = os.path.join(backup_path, "backup_metadata.json")
                    if os.path.exists(metadata_file):
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        backup_dirs.append((metadata["timestamp"], backup_path))
            
            # Сортируем по времени и удаляем старые
            backup_dirs.sort(key=lambda x: x[0], reverse=True)
            
            if len(backup_dirs) > self.max_backups:
                for _, old_backup_path in backup_dirs[self.max_backups:]:
                    shutil.rmtree(old_backup_path)
                    logger.debug("🗑️ Удалена старая резервная копия: %s", os.path.basename(old_backup_path))
        
        except Exception as e:
            logger.error("❌ Ошибка очистки старых резервных копий: %s", e)
    
    async def cleanup_old_files(self, max_age_days: int = 30):
        """Очищает старые файлы и логи"""
        try:
            cutoff_time = time.time() - (max_age_days * 24 * 3600)
            cleaned_files = 0
            
            # Очищаем старые логи
            logs_dir = os.path.join(self.base_dir, "logs")
            if os.path.exists(logs_dir):
                for filename in os.listdir(logs_dir):
                    file_path = os.path.join(logs_dir, filename)
                    if os.path.isfile(file_path):
                        file_mtime = os.path.getmtime(file_path)
                        if file_mtime < cutoff_time:
                            os.remove(file_path)
                            cleaned_files += 1
            
            # Очищаем старые экспорты
            exports_dir = os.path.join(self.base_dir, "exports")
            if os.path.exists(exports_dir):
                for filename in os.listdir(exports_dir):
                    file_path = os.path.join(exports_dir, filename)
                    if os.path.isfile(file_path):
                        file_mtime = os.path.getmtime(file_path)
                        if file_mtime < cutoff_time:
                            os.remove(file_path)
                            cleaned_files += 1
            
            if cleaned_files > 0:
                logger.info("🧹 Очищено старых файлов: %d (старше %d дней)", cleaned_files, max_age_days)
        
        except Exception as e:
            logger.error("❌ Ошибка очистки старых файлов: %s", e)
    
    def _get_directory_size(self, directory: str) -> int:
        """Получает размер директории в байтах"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    if os.path.exists(file_path):
                        total_size += os.path.getsize(file_path)
        except Exception as e:
            logger.error("❌ Ошибка расчета размера директории: %s", e)
        
        return total_size
    
    async def export_data(self, export_format: str = "json") -> Optional[str]:
        """
        Экспортирует данные AI-системы
        
        Args:
            export_format: Формат экспорта ("json", "csv")
        
        Returns:
            Путь к экспортированному файлу
        """
        try:
            timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"ai_data_export_{timestamp}.{export_format}"
            export_path = os.path.join(self.base_dir, "exports", export_filename)
            
            # Собираем все данные
            export_data = await self.load_state()
            export_data["export_metadata"] = {
                "timestamp": time.time(),
                "datetime": timestamp,
                "format": export_format,
                "version": "1.0"
            }
            
            if export_format == "json":
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            else:
                logger.warning("⚠️ Неподдерживаемый формат экспорта: %s", export_format)
                return None
            
            logger.info("📤 Данные экспортированы: %s", export_filename)
            return export_path
        
        except Exception as e:
            logger.error("❌ Ошибка экспорта данных: %s", e)
            return None
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Получает информацию о состоянии системы"""
        try:
            health_info = {
                "timestamp": time.time(),
                "directories": {},
                "files": {},
                "backups": {},
                "disk_usage": {}
            }
            
            # Проверяем директории
            directories = [self.base_dir, self.backup_dir]
            for directory in directories:
                health_info["directories"][directory] = {
                    "exists": os.path.exists(directory),
                    "writable": os.access(directory, os.W_OK) if os.path.exists(directory) else False,
                    "size_mb": self._get_directory_size(directory) / (1024 * 1024) if os.path.exists(directory) else 0
                }
            
            # Проверяем основные файлы
            files = [self.state_file, self.pattern_file]
            for file_path in files:
                health_info["files"][os.path.basename(file_path)] = {
                    "exists": os.path.exists(file_path),
                    "size_kb": os.path.getsize(file_path) / 1024 if os.path.exists(file_path) else 0,
                    "last_modified": os.path.getmtime(file_path) if os.path.exists(file_path) else 0
                }
            
            # Информация о резервных копиях
            if os.path.exists(self.backup_dir):
                backup_count = len([d for d in os.listdir(self.backup_dir) 
                                  if os.path.isdir(os.path.join(self.backup_dir, d)) and d.startswith("backup_")])
                health_info["backups"] = {
                    "count": backup_count,
                    "last_backup_age_hours": (time.time() - self.last_backup_time) / 3600,
                    "total_size_mb": health_info["directories"][self.backup_dir]["size_mb"]
                }
            
            return health_info
        
        except Exception as e:
            logger.error("❌ Ошибка получения состояния системы: %s", e)
            return {"error": str(e)}


# Глобальный экземпляр менеджера состояния
state_manager: Optional[AIStateManager] = None


def get_state_manager() -> AIStateManager:
    """Получает глобальный экземпляр менеджера состояния"""
    global state_manager
    
    if state_manager is None:
        state_manager = AIStateManager()
    
    return state_manager
