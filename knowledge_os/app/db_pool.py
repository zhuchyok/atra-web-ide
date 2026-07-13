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

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os?application_name=knowledge_pool",
)
AGENT_TEAMS_PILOT_CONTEXT = os.getenv("AGENT_TEAMS_PILOT_CONTEXT", "pilot:agent-teams-v1").strip()
AGENT_TEAMS_PILOT_TAG = os.getenv("AGENT_TEAMS_PILOT_TAG", "agent-teams-v1").strip()

# Читаем из env, чтобы можно было тюнить без rebuild (например, при включённом PgBouncer ставим 20)
_MAX_POOL_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
_MIN_POOL_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
_CONNECT_RETRIES = int(os.getenv("DB_POOL_CONNECT_RETRIES", "5"))
_RETRY_BASE_DELAY_SEC = float(os.getenv("DB_POOL_RETRY_BASE_DELAY_SEC", "1.0"))

_pool = None


def _is_transient_connect_error(err: Exception) -> bool:
    msg = str(err).lower()
    markers = (
        "temporary failure in name resolution",
        "name or service not known",
        "could not translate host name",
        "connection refused",
        "timed out",
        "timeout",
        "failed to resolve",
        "nodename nor servname",
    )
    return any(m in msg for m in markers)


async def get_pool():
    """Ленивая инициализация пула. Возвращает asyncpg Pool (или в будущем — обёртку над Rust)."""
    global _pool
    if _pool is None:
        last_error = None
        for attempt in range(1, max(1, _CONNECT_RETRIES) + 1):
            try:
                _pool = await asyncpg.create_pool(
                    DB_URL,
                    min_size=_MIN_POOL_SIZE,
                    max_size=_MAX_POOL_SIZE,
                    max_inactive_connection_lifetime=300,
                    command_timeout=30,
                )
                break
            except Exception as err:
                last_error = err
                if not _is_transient_connect_error(err) or attempt >= _CONNECT_RETRIES:
                    raise
                delay = _RETRY_BASE_DELAY_SEC * attempt
                logger.warning(
                    "[DB_POOL] transient connect error (attempt %s/%s): %s. retry in %.1fs",
                    attempt,
                    _CONNECT_RETRIES,
                    err,
                    delay,
                )
                await asyncio.sleep(delay)
        if _pool is None and last_error:
            raise last_error
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
    if not isinstance(meta, dict):
        try:
            meta = dict(meta)
        except Exception:
            meta = {}

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
    if project_context and project_context.strip() == AGENT_TEAMS_PILOT_CONTEXT:
        # Normalize pilot cohort tagging so orchestrator and workers can apply
        # strict guardrails using a stable metadata marker.
        meta.setdefault("pilot", AGENT_TEAMS_PILOT_TAG)
        meta.setdefault("pilot_context", AGENT_TEAMS_PILOT_CONTEXT)

    async with pool.acquire() as conn:
        # Safeguard: target_expert must refer to the assignee executor, not to subject/persona.
        # If assignee is known and target_expert mismatches, normalize to assignee and preserve original.
        assignee_name = None
        if assignee_expert_id:
            try:
                assignee_name = await conn.fetchval(
                    "SELECT name FROM experts WHERE id = $1 LIMIT 1", assignee_expert_id
                )
            except Exception as resolve_err:
                logger.debug("[TASK-GUARD] failed to resolve assignee name: %s", resolve_err)
        if assignee_name:
            raw_target = meta.get("target_expert")
            if isinstance(raw_target, str):
                raw_target = raw_target.strip()
            if raw_target and raw_target != assignee_name:
                meta["target_expert_original"] = raw_target
                if not meta.get("subject_expert"):
                    meta["subject_expert"] = raw_target
                meta["target_expert"] = assignee_name
                meta["target_expert_normalized"] = True
                logger.warning(
                    "[TASK-GUARD] normalized target_expert '%s' -> '%s' for task title='%s'",
                    raw_target,
                    assignee_name,
                    title[:80],
                )
            elif not raw_target:
                meta["target_expert"] = assignee_name

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
            now,
        )

        if task_id:
            logger.info(f"✅ Задача создана: {title} (ID: {task_id})")
        else:
            logger.debug(f"⏭️ Пропуск дубликата задачи: {title} (context: {project_context})")

        return task_id
