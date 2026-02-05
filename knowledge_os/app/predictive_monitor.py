"""
Predictive Monitor — предиктивный мониторинг трендов (Living Organism §6, Singularity 10.0).

Анализирует тренды: рост in_progress без завершения, рост очереди pending.
При превышении порогов — создание задач для SRE.
Мировые практики: предиктивные алерты до возникновения инцидента.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

# Пороги (env для настройки)
STUCK_MINUTES = int(os.getenv("PREDICTIVE_STUCK_MINUTES", "15"))
STUCK_COUNT_THRESHOLD = int(os.getenv("PREDICTIVE_STUCK_COUNT_THRESHOLD", "5"))
PENDING_HOURS = int(os.getenv("PREDICTIVE_PENDING_HOURS", "1"))
PENDING_COUNT_THRESHOLD = int(os.getenv("PREDICTIVE_PENDING_COUNT_THRESHOLD", "30"))


async def _create_predictive_task(conn, title: str, description: str, assignee_hint: str = "SRE") -> bool:
    """Создаёт задачу от Predictive Monitor. Избегает дублирования за 24ч."""
    try:
        existing = await conn.fetchval("""
            SELECT 1 FROM tasks
            WHERE title = $1 AND created_at > NOW() - INTERVAL '24 hours'
            LIMIT 1
        """, title)
        if existing:
            return False
        metadata = json.dumps({"source": "predictive_monitor", "assignee_hint": assignee_hint})
        await conn.execute("""
            INSERT INTO tasks (title, description, status, priority, metadata)
            VALUES ($1, $2, 'pending', 'high', $3::jsonb)
        """, title, description, metadata)
        logger.info("📋 [PREDICTIVE] Создана задача: %s", title)
        return True
    except Exception as e:
        logger.warning("Ошибка создания задачи predictive_monitor: %s", e)
        return False


async def run_predictive_check() -> Dict[str, Any]:
    """
    Запуск предиктивной проверки трендов.
    - Задачи in_progress без обновления > STUCK_MINUTES
    - Задачи pending старше PENDING_HOURS
    При превышении порогов — создаёт задачи в БД.
    """
    try:
        import asyncpg
    except ImportError:
        logger.debug("asyncpg не доступен, пропускаем predictive_check")
        return {"tasks_created": 0, "stuck_count": 0, "old_pending_count": 0}

    result: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "stuck_count": 0,
        "old_pending_count": 0,
        "tasks_created": 0,
        "alerts": [],
    }

    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            # 1) Зависшие in_progress (без обновления > N минут)
            stuck_count = await conn.fetchval("""
                SELECT COUNT(*) FROM tasks
                WHERE status = 'in_progress'
                  AND updated_at < NOW() - INTERVAL '1 minute' * $1
            """, STUCK_MINUTES)
            result["stuck_count"] = stuck_count or 0

            if (stuck_count or 0) >= STUCK_COUNT_THRESHOLD:
                title = "🔧 Predictive: проверить зависшие задачи (in_progress без обновления)"
                desc = f"Задач в статусе in_progress без обновления более {STUCK_MINUTES} минут: {stuck_count}. Порог: {STUCK_COUNT_THRESHOLD}. Проверить воркер, MLX/Ollama, сброс зависших."
                if await _create_predictive_task(conn, title, desc, "SRE"):
                    result["tasks_created"] += 1
                    result["alerts"].append("stuck_tasks")

            # 2) Старые pending (не назначены, в очереди > N часов)
            old_pending = await conn.fetchval("""
                SELECT COUNT(*) FROM tasks
                WHERE status = 'pending'
                  AND created_at < NOW() - INTERVAL '1 hour' * $1
            """, PENDING_HOURS)
            result["old_pending_count"] = old_pending or 0

            if (old_pending or 0) >= PENDING_COUNT_THRESHOLD:
                title = "🔧 Predictive: проверить очередь pending (задачи старше порога)"
                desc = f"Задач pending старше {PENDING_HOURS} ч: {old_pending}. Порог: {PENDING_COUNT_THRESHOLD}. Проверить оркестратор, назначение экспертам, приоритеты."
                if await _create_predictive_task(conn, title, desc, "SRE"):
                    result["tasks_created"] += 1
                    result["alerts"].append("old_pending")

        finally:
            await conn.close()
    except Exception as e:
        logger.warning("predictive_monitor failed: %s", e)
        result["error"] = str(e)

    return result
