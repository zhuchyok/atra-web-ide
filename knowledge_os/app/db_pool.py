"""
Единая точка доступа к пулу БД Knowledge OS.

Используется в rest_api, collective_memory и др. При будущем переводе на Rust
здесь можно заменить asyncpg на обёртку над Rust-пулом (тот же контракт: get_pool() -> pool, pool.acquire()).

Best practices (2026, 12-Factor + asyncpg):
- max_size=5: при 39+ модулях каждый с пулом суммарный лимит ~300-400 → легко достигает max_connections=500.
  Уменьшение до 5 снижает пиковое потребление; при необходимости — PgBouncer перед Postgres.
- max_inactive_connection_lifetime=300: закрывает idle-соединения через 5 мин (освобождает слоты).
- command_timeout=30: гарантирует, что зависший запрос не держит соединение вечно.
"""

import os

import json
import logging
from datetime import datetime, timezone

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os?application_name=knowledge_pool")

# Читаем из env, чтобы можно было тюнить без rebuild (например, при включённом PgBouncer ставим 20)
_MAX_POOL_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
_MIN_POOL_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "2"))

_pool = None


async def get_pool():
    """Ленивая инициализация пула. Возвращает asyncpg Pool (или в будущем — обёртку над Rust)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DB_URL,
            min_size=_MIN_POOL_SIZE,
            max_size=_MAX_POOL_SIZE,
            max_inactive_connection_lifetime=300,
            command_timeout=30,
        )
    return _pool


async def close_pool():
    """Явное закрытие пула при shutdown (освобождает все соединения сразу)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def create_task_safe(
    title: str,
    description: str,
    status: str = "pending",
    priority: str = "medium",
    project_context: str = "default",
    creator_expert_id: str = None,
    assignee_expert_id: str = None,
    domain_id: str = None,
    metadata: dict = None,
    parent_task_id: str = None,
) -> str:
    """
    Безопасное создание задачи с дедупликацией на уровне БД.
    Использует ON CONFLICT DO NOTHING для предотвращения дублей в PENDING/IN_PROGRESS.
    """
    pool = await get_pool()
    meta = metadata or {}
    
    query = """
        INSERT INTO tasks (
            title, description, status, priority, project_context, 
            creator_expert_id, assignee_expert_id, domain_id, metadata, 
            parent_task_id, created_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10, $11, $11)
        ON CONFLICT (title, COALESCE(project_context, 'default')) 
        WHERE status IN ('pending', 'in_progress') 
        DO NOTHING
        RETURNING id;
    """
    
    now = datetime.now(timezone.utc)
    
    async with pool.acquire() as conn:
        task_id = await conn.fetchval(
            query,
            title,
            description,
            status,
            priority,
            project_context,
            creator_expert_id,
            assignee_expert_id,
            domain_id,
            json.dumps(meta),
            parent_task_id,
            now
        )
        
        if task_id:
            logger.info(f"✅ Задача создана: {title} (ID: {task_id})")
        else:
            logger.debug(f"⏭️ Пропуск дубликата задачи: {title} (context: {project_context})")
            
        return task_id
