"""
Extracted phases from run_enhanced_orchestration_cycle (enhanced_orchestrator.py).
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


async def has_execution_backlog(conn) -> bool:
    """Fast check: there is work to do (pending or in_progress tasks)."""
    try:
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE status = 'pending' AND created_at > NOW() - INTERVAL '1 hour'"
        )
        in_progress = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE status = 'in_progress' AND created_at > NOW() - INTERVAL '2 hours'"
        )
        return (pending or 0) > 0 or (in_progress or 0) > 0
    except Exception as e:
        logger.debug(f"Backlog check failed: {e}")
        return True


async def check_llm_health() -> Tuple[bool, bool]:
    """Check Ollama and MLX health."""
    ollama_ok = mlx_ok = False
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(
                os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434") + "/api/tags"
            )
            ollama_ok = r.status_code == 200
    except Exception:
        pass
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(
                os.getenv("MLX_BASE_URL", "http://host.docker.internal:11435") + "/health"
            )
            mlx_ok = r.status_code == 200
    except Exception:
        pass
    return ollama_ok, mlx_ok


async def prioritize_tasks(conn, victoria_id: str) -> int:
    """Prioritize unassigned pending tasks."""
    updated = 0
    try:
        tasks = await conn.fetch(
            """SELECT id, goal, priority, created_at FROM tasks
               WHERE assignee_expert_id IS NULL AND status = 'pending'
               AND priority IS NULL OR priority = '' ORDER BY created_at ASC LIMIT 50"""
        )
        for task in tasks:
            new_priority = await _calc_priority(task["goal"] or "")
            if new_priority:
                await conn.execute(
                    "UPDATE tasks SET priority = $1, updated_at = NOW() WHERE id = $2",
                    new_priority,
                    task["id"],
                )
                updated += 1
    except Exception as e:
        logger.debug(f"Prioritize failed: {e}")
    return updated


async def _calc_priority(goal: str) -> Optional[str]:
    """Simple priority calculation based on keywords."""
    g = goal.lower()
    if any(w in g for w in ["срочн", "critical", "urgent", "авар"]):
        return "urgent"
    if any(w in g for w in ["важн", "high", "баг", "bug", "ошибк"]):
        return "high"
    return None


async def get_default_expert_id(conn) -> str:
    """Get Victoria's expert ID as default."""
    vid = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
    if not vid:
        vid = await conn.fetchval("SELECT id FROM experts ORDER BY created_at ASC LIMIT 1")
    return str(vid) if vid else ""
