"""
Auto Backup Manager для автоматических бэкапов базы данных и критичных данных.
Создает бэкапы по расписанию и при критичных изменениях.
"""

import asyncio
import os
import logging
import shutil
import subprocess
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

class AutoBackupManager:
    """
    Автоматический менеджер бэкапов.
    Создает бэкапы БД и критичных данных по расписанию.
    """
    
    def __init__(
        self,
        db_url: str,
        backup_dir: str = "backups",
        max_backups: int = 30,  # Храним 30 бэкапов
        backup_interval_hours: int = 6  # Бэкап каждые 6 часов
    ):
        self.db_url = db_url
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.backup_interval_hours = backup_interval_hours
        
        # Создаем директорию для бэкапов
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self._last_backup_time: Optional[datetime] = None
        self._running = False
        self._backup_task: Optional[asyncio.Task] = None
    
    async def create_backup(
        self,
        backup_type: str = "scheduled",
        force: bool = False
    ) -> Optional[str]:
        """
        Создает бэкап базы данных.
        
        Args:
            backup_type: Тип бэкапа ('scheduled', 'manual', 'critical')
            force: Принудительно создать бэкап, даже если недавно был
        
        Returns:
            Путь к созданному бэкапу или None при ошибке
        """
        # Проверяем, нужно ли создавать бэкап
        if not force and self._last_backup_time:
            time_since_last = datetime.now() - self._last_backup_time
            if time_since_last.total_seconds() < 3600:  # Минимум 1 час между бэкапами
                logger.debug("⏭️ Пропуск бэкапа: недавно был создан бэкап")
                return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"knowledge_os_backup_{backup_type}_{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Создаем бэкап через pg_dump
            logger.info(f"💾 Создание бэкапа: {backup_path}")
            
            # Парсим DATABASE_URL
            # Формат: postgresql://user:password@host:port/database
            if "postgresql://" in self.db_url:
                # Извлекаем компоненты
                db_url_clean = self.db_url.replace("postgresql://", "")
                if "@" in db_url_clean:
                    auth, rest = db_url_clean.split("@", 1)
                    if ":" in auth:
                        user, password = auth.split(":", 1)
                    else:
                        user = auth
                        password = None
                    
                    if "/" in rest:
                        host_port, database = rest.split("/", 1)
                        if ":" in host_port:
                            host, port = host_port.split(":", 1)
                        else:
                            host = host_port
                            port = "5432"
                    else:
                        host = rest
                        port = "5432"
                        database = "knowledge_os"
                else:
                    # Упрощенный формат
                    parts = db_url_clean.split("/")
                    database = parts[-1] if len(parts) > 1 else "knowledge_os"
                    host = parts[0].split(":")[0] if ":" in parts[0] else "localhost"
                    port = parts[0].split(":")[1] if ":" in parts[0] else "5432"
                    user = os.getenv("DB_USER", "admin")
                    password = None
                
                # Создаем команду pg_dump
                env = os.environ.copy()
                if password:
                    env["PGPASSWORD"] = password
                
                cmd = [
                    "pg_dump",
                    "-h", host,
                    "-p", port,
                    "-U", user,
                    "-d", database,
                    "-F", "c",  # Custom format
                    "-f", str(backup_path)
                ]
                
                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 минут таймаут
                )
                
                if result.returncode == 0:
                    # Проверяем размер файла
                    if backup_path.exists() and backup_path.stat().st_size > 0:
                        self._last_backup_time = datetime.now()
                        logger.info(f"✅ Бэкап создан: {backup_path} ({backup_path.stat().st_size / 1024 / 1024:.2f} MB)")
                        
                        # Ротируем старые бэкапы
                        await self._rotate_backups()
                        
                        return str(backup_path)
                    else:
                        logger.error(f"❌ Бэкап создан, но файл пустой: {backup_path}")
                        if backup_path.exists():
                            backup_path.unlink()
                else:
                    logger.error(f"❌ Ошибка создания бэкапа: {result.stderr}")
            
            else:
                # SQLite бэкап (если используется SQLite)
                logger.warning("⚠️ SQLite бэкап не реализован, используйте PostgreSQL")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Таймаут при создании бэкапа")
            if backup_path.exists():
                backup_path.unlink()
        except Exception as e:
            logger.error(f"❌ Ошибка создания бэкапа: {e}")
            if backup_path.exists():
                backup_path.unlink()
        
        return None
    
    async def _rotate_backups(self):
        """Удаляет старые бэкапы, оставляя только последние N"""
        try:
            backups = sorted(
                self.backup_dir.glob("knowledge_os_backup_*.sql"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            if len(backups) > self.max_backups:
                for old_backup in backups[self.max_backups:]:
                    logger.info(f"🗑️ Удаление старого бэкапа: {old_backup}")
                    old_backup.unlink()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка ротации бэкапов: {e}")
    
    async def restore_backup(self, backup_path: str) -> bool:
        """
        Восстанавливает базу данных из бэкапа.
        
        Args:
            backup_path: Путь к файлу бэкапа
        
        Returns:
            True если успешно восстановлено
        """
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"❌ Файл бэкапа не найден: {backup_path}")
            return False
        
        try:
            logger.info(f"🔄 Восстановление из бэкапа: {backup_path}")
            
            # Парсим DATABASE_URL (аналогично create_backup)
            if "postgresql://" in self.db_url:
                # Извлекаем компоненты (упрощенная версия)
                db_url_clean = self.db_url.replace("postgresql://", "")
                if "@" in db_url_clean:
                    auth, rest = db_url_clean.split("@", 1)
                    user = auth.split(":")[0] if ":" in auth else auth
                    password = auth.split(":")[1] if ":" in auth else None
                    
                    if "/" in rest:
                        host_port, database = rest.split("/", 1)
                        host = host_port.split(":")[0] if ":" in host_port else host_port
                        port = host_port.split(":")[1] if ":" in host_port else "5432"
                    else:
                        host = rest
                        port = "5432"
                        database = "knowledge_os"
                else:
                    host = "localhost"
                    port = "5432"
                    database = "knowledge_os"
                    user = os.getenv("DB_USER", "admin")
                    password = None
                
                env = os.environ.copy()
                if password:
                    env["PGPASSWORD"] = password
                
                # Восстанавливаем через pg_restore
                cmd = [
                    "pg_restore",
                    "-h", host,
                    "-p", port,
                    "-U", user,
                    "-d", database,
                    "-c",  # Clean (drop objects before creating)
                    str(backup_file)
                ]
                
                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 минут таймаут
                )
                
                if result.returncode == 0:
                    logger.info(f"✅ База данных восстановлена из бэкапа: {backup_path}")
                    return True
                else:
                    logger.error(f"❌ Ошибка восстановления: {result.stderr}")
                    return False
            else:
                logger.warning("⚠️ Восстановление SQLite не реализовано")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления из бэкапа: {e}")
            return False
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """Возвращает список доступных бэкапов"""
        backups = []
        for backup_file in sorted(
            self.backup_dir.glob("knowledge_os_backup_*.sql"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            backups.append({
                "path": str(backup_file),
                "filename": backup_file.name,
                "size_mb": backup_file.stat().st_size / 1024 / 1024,
                "created_at": datetime.fromtimestamp(backup_file.stat().st_mtime)
            })
        return backups
    
    async def monitor_and_backup(self):
        """Мониторинг и автоматическое создание бэкапов"""
        self._running = True
        logger.info("🔄 Запущен автоматический мониторинг бэкапов")
        
        while self._running:
            try:
                # Проверяем, нужно ли создать бэкап
                if not self._last_backup_time:
                    # Первый бэкап при запуске
                    await self.create_backup("scheduled", force=True)
                else:
                    time_since_last = datetime.now() - self._last_backup_time
                    if time_since_last.total_seconds() >= self.backup_interval_hours * 3600:
                        await self.create_backup("scheduled", force=True)
                
                # Ждем до следующей проверки (проверяем каждый час)
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в мониторинге бэкапов: {e}")
                await asyncio.sleep(3600)
    
    def start_monitoring(self):
        """Запустить мониторинг бэкапов"""
        if not self._running:
            self._backup_task = asyncio.create_task(self.monitor_and_backup())
    
    def stop_monitoring(self):
        """Остановить мониторинг бэкапов"""
        self._running = False
        if self._backup_task:
            self._backup_task.cancel()

# Глобальный экземпляр
_auto_backup_manager: Optional[AutoBackupManager] = None

def get_auto_backup_manager(
    db_url: str = None,
    backup_dir: str = "backups"
) -> AutoBackupManager:
    """Получить глобальный экземпляр AutoBackupManager"""
    global _auto_backup_manager
    if _auto_backup_manager is None:
        db_url = db_url or os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
        _auto_backup_manager = AutoBackupManager(db_url, backup_dir)
    return _auto_backup_manager

