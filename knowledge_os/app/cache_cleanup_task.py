"""
Cache Cleanup Task
Фоновая задача для автоматической очистки устаревших записей кэша
Singularity 8.0: Performance Optimization
"""

import asyncio
import logging
import asyncpg
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class CacheCleanupTask:
    """
    Автоматическая очистка устаревших записей кэша.
    Запускается каждые 30 минут.
    """
    
    def __init__(self, db_url: str = DB_URL, cleanup_interval: int = 1800):
        """
        Args:
            db_url: URL базы данных
            cleanup_interval: Интервал очистки в секундах (по умолчанию 30 минут)
        """
        self.db_url = db_url
        self.cleanup_interval = cleanup_interval
        self._running = False
        self._task = None
    
    async def cleanup_expired_cache(self) -> int:
        """
        Удаляет устаревшие записи из кэша.
        
        Returns:
            Количество удаленных записей
        """
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие колонки expires_at
                has_expires_at = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'semantic_ai_cache' 
                        AND column_name = 'expires_at'
                    )
                """)
                
                if not has_expires_at:
                    logger.debug("⚠️ [CACHE CLEANUP] Колонка expires_at не найдена, пропускаем очистку")
                    return 0
                
                # Удаляем устаревшие записи
                deleted_count = await conn.execute("""
                    DELETE FROM semantic_ai_cache
                    WHERE expires_at IS NOT NULL 
                    AND expires_at < NOW()
                """)
                
                # Получаем количество удаленных записей
                deleted_rows = int(deleted_count.split()[-1]) if deleted_count else 0
                
                if deleted_rows > 0:
                    logger.info(f"🧹 [CACHE CLEANUP] Удалено {deleted_rows} устаревших записей")
                else:
                    logger.debug("✅ [CACHE CLEANUP] Устаревших записей не найдено")
                
                return deleted_rows
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [CACHE CLEANUP] Ошибка очистки кэша: {e}")
            return 0
    
    async def start(self):
        """Запускает фоновую задачу очистки"""
        if self._running:
            logger.warning("⚠️ [CACHE CLEANUP] Задача уже запущена")
            return
        
        self._running = True
        logger.info(f"🚀 [CACHE CLEANUP] Запуск фоновой задачи очистки (интервал: {self.cleanup_interval}s)")
        
        async def cleanup_loop():
            while self._running:
                try:
                    await self.cleanup_expired_cache()
                except Exception as e:
                    logger.error(f"❌ [CACHE CLEANUP] Ошибка в цикле очистки: {e}")
                
                await asyncio.sleep(self.cleanup_interval)
        
        self._task = asyncio.create_task(cleanup_loop())
    
    async def stop(self):
        """Останавливает фоновую задачу"""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 [CACHE CLEANUP] Фоновая задача остановлена")

# Singleton instance
_cleanup_task_instance: CacheCleanupTask = None

def get_cache_cleanup_task(cleanup_interval: int = 1800) -> CacheCleanupTask:
    """Получить singleton экземпляр задачи очистки"""
    global _cleanup_task_instance
    if _cleanup_task_instance is None:
        _cleanup_task_instance = CacheCleanupTask(cleanup_interval=cleanup_interval)
    return _cleanup_task_instance

