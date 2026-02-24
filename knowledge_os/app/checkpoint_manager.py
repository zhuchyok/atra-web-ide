"""
Checkpoint Manager - Управление точками восстановления
Сохранение состояния для длительных задач и восстановление после сбоев
"""

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Попытка использовать БД
try:
    import asyncpg

    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.debug(
        "ℹ️ asyncpg не доступен, checkpoint'ы будут храниться в памяти (опциональный компонент)"
    )


@dataclass
class Checkpoint:
    """Точка восстановления"""

    checkpoint_id: str
    task_id: str
    agent_name: str
    state: Dict[str, Any]
    step: int
    progress: float  # 0.0-1.0
    metadata: Dict[str, Any]
    created_at: datetime
    expires_at: Optional[datetime] = None


class CheckpointManager:
    """Менеджер checkpoint'ов"""

    def __init__(self, db_url: Optional[str] = None, default_ttl_hours: int = 24):
        self.db_url = db_url or os.getenv("DATABASE_URL")
        self.default_ttl_hours = default_ttl_hours
        self.checkpoints: Dict[str, Checkpoint] = {}
        self._db_pool = None

    async def _init_db(self):
        """Инициализация БД для checkpoint'ов"""
        if not DB_AVAILABLE or not self.db_url:
            return

        try:
            self._db_pool = await asyncpg.create_pool(self.db_url)

            # Создаем таблицу если не существует
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        checkpoint_id VARCHAR(255) PRIMARY KEY,
                        task_id VARCHAR(255) NOT NULL,
                        agent_name VARCHAR(100) NOT NULL,
                        state JSONB NOT NULL,
                        step INTEGER NOT NULL,
                        progress FLOAT NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                        expires_at TIMESTAMP WITH TIME ZONE
                    );

                    CREATE INDEX IF NOT EXISTS idx_checkpoints_task_id ON checkpoints(task_id);
                    CREATE INDEX IF NOT EXISTS idx_checkpoints_agent ON checkpoints(agent_name);
                """)
            logger.info("✅ Таблица checkpoints создана")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать БД для checkpoint'ов: {e}")

    async def create_checkpoint(
        self,
        task_id: str,
        agent_name: str,
        state: Dict[str, Any],
        step: int,
        progress: float,
        metadata: Dict[str, Any] = None,
        ttl_hours: Optional[int] = None,
    ) -> Checkpoint:
        """
        Создать checkpoint

        Args:
            task_id: ID задачи
            agent_name: Имя агента
            state: Состояние для сохранения
            step: Номер шага
            progress: Прогресс (0.0-1.0)
            metadata: Дополнительные метаданные
            ttl_hours: Время жизни в часах

        Returns:
            Checkpoint объект
        """
        checkpoint_id = f"checkpoint_{task_id}_{step}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        ttl = ttl_hours or self.default_ttl_hours
        expires_at = (
            datetime.now(timezone.utc).replace(hour=datetime.now(timezone.utc).hour + ttl)
            if ttl > 0
            else None
        )

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            agent_name=agent_name,
            state=state,
            step=step,
            progress=progress,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
        )

        # Сохраняем в память
        self.checkpoints[checkpoint_id] = checkpoint

        # Сохраняем в БД
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO checkpoints
                        (checkpoint_id, task_id, agent_name, state, step, progress, metadata, created_at, expires_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (checkpoint_id) DO UPDATE SET
                            state = EXCLUDED.state,
                            step = EXCLUDED.step,
                            progress = EXCLUDED.progress,
                            metadata = EXCLUDED.metadata,
                            expires_at = EXCLUDED.expires_at
                    """,
                        checkpoint_id,
                        task_id,
                        agent_name,
                        json.dumps(state),
                        step,
                        progress,
                        json.dumps(metadata or {}),
                        checkpoint.created_at,
                        checkpoint.expires_at,
                    )
            except Exception as e:
                logger.warning(f"⚠️ Не удалось сохранить checkpoint в БД: {e}")

        logger.info(f"💾 Checkpoint создан: {checkpoint_id} (шаг {step}, прогресс {progress:.1%})")

        return checkpoint

    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Получить checkpoint по ID"""
        # Проверяем в памяти
        if checkpoint_id in self.checkpoints:
            checkpoint = self.checkpoints[checkpoint_id]
            # Проверяем срок действия
            if checkpoint.expires_at and checkpoint.expires_at < datetime.now(timezone.utc):
                del self.checkpoints[checkpoint_id]
                return None
            return checkpoint

        # Проверяем в БД
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM checkpoints
                        WHERE checkpoint_id = $1
                        AND (expires_at IS NULL OR expires_at > NOW())
                    """,
                        checkpoint_id,
                    )

                    if row:
                        checkpoint = Checkpoint(
                            checkpoint_id=row["checkpoint_id"],
                            task_id=row["task_id"],
                            agent_name=row["agent_name"],
                            state=json.loads(row["state"]),
                            step=row["step"],
                            progress=row["progress"],
                            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                            created_at=row["created_at"],
                            expires_at=row["expires_at"],
                        )
                        self.checkpoints[checkpoint_id] = checkpoint
                        return checkpoint
            except Exception as e:
                logger.warning(f"⚠️ Ошибка получения checkpoint из БД: {e}")

        return None

    async def get_latest_checkpoint(self, task_id: str) -> Optional[Checkpoint]:
        """Получить последний checkpoint для задачи"""
        # Проверяем в памяти
        task_checkpoints = [
            cp
            for cp in self.checkpoints.values()
            if cp.task_id == task_id
            and (not cp.expires_at or cp.expires_at > datetime.now(timezone.utc))
        ]

        if task_checkpoints:
            return max(task_checkpoints, key=lambda cp: cp.step)

        # Проверяем в БД
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM checkpoints
                        WHERE task_id = $1
                        AND (expires_at IS NULL OR expires_at > NOW())
                        ORDER BY step DESC
                        LIMIT 1
                    """,
                        task_id,
                    )

                    if row:
                        checkpoint = Checkpoint(
                            checkpoint_id=row["checkpoint_id"],
                            task_id=row["task_id"],
                            agent_name=row["agent_name"],
                            state=json.loads(row["state"]),
                            step=row["step"],
                            progress=row["progress"],
                            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                            created_at=row["created_at"],
                            expires_at=row["expires_at"],
                        )
                        self.checkpoints[checkpoint_id] = checkpoint
                        return checkpoint
            except Exception as e:
                logger.warning(f"⚠️ Ошибка получения checkpoint из БД: {e}")

        return None

    async def restore_from_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """
        Восстановить состояние из checkpoint

        Args:
            checkpoint_id: ID checkpoint'а

        Returns:
            Сохраненное состояние или None
        """
        checkpoint = await self.get_checkpoint(checkpoint_id)

        if checkpoint:
            logger.info(f"🔄 Восстановление из checkpoint: {checkpoint_id} (шаг {checkpoint.step})")
            return checkpoint.state

        return None

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Удалить checkpoint"""
        # Удаляем из памяти
        if checkpoint_id in self.checkpoints:
            del self.checkpoints[checkpoint_id]

        # Удаляем из БД
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM checkpoints WHERE checkpoint_id = $1", checkpoint_id
                    )
            except Exception as e:
                logger.warning(f"⚠️ Ошибка удаления checkpoint из БД: {e}")

        return True

    async def cleanup_expired(self):
        """Очистить истекшие checkpoint'ы"""
        now = datetime.now(timezone.utc)

        # Очистка в памяти
        expired_ids = [
            cp_id for cp_id, cp in self.checkpoints.items() if cp.expires_at and cp.expires_at < now
        ]
        for cp_id in expired_ids:
            del self.checkpoints[cp_id]

        # Очистка в БД
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    deleted = await conn.execute("DELETE FROM checkpoints WHERE expires_at < NOW()")
                    logger.info(f"🗑️ Удалено истекших checkpoint'ов: {deleted}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка очистки checkpoint'ов в БД: {e}")


# Глобальный экземпляр
_checkpoint_manager: Optional[CheckpointManager] = None


async def get_checkpoint_manager() -> CheckpointManager:
    """Получить глобальный экземпляр CheckpointManager"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = CheckpointManager()
        await _checkpoint_manager._init_db()
    return _checkpoint_manager
