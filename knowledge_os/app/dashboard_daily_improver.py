"""
Dashboard Daily Improver — ежедневный анализ и улучшение дашборда экспертами (Singularity 10.0)

Эксперты (Frontend, UX, QA, Performance, Product) анализируют:
- Ошибки: пустые состояния, падения при отсутствии данных
- Недочёты: дублирование метрик, избыточные запросы
- Параметры: какие выводятся, полезны ли
- Страницы: структура, иерархия, навигация
- Производительность: st.cache_data max_entries, LEFT(content,N), lazy load

Мировые практики: Streamlit best practices, Grafana/McKinsey dashboards
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"
_DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


async def _create_dashboard_improvement_tasks(conn) -> int:
    """Создаёт задачи на улучшение дашборда в tasks."""
    try:
        import asyncpg
    except ImportError:
        return 0

    tasks_created = 0
    # Чеклист для ежедневного прогона (можно расширить через LLM)
    checklist = [
        ("Проверить max_entries в st.cache_data", "medium", "Frontend/Performance", "DASHBOARD_OPTIMIZATION_PLAN: max_entries=100"),
        ("Проверить LEFT(content,N) в запросах к knowledge_nodes", "medium", "Backend", "Избегать загрузки полного content"),
        ("Проверить lazy load вкладок (st.fragment)", "low", "Frontend", "Streamlit best practices"),
        ("Проверить пустые состояния и fallback при отсутствии данных", "high", "QA", "Ошибки: пустые состояния"),
        ("Проверить дублирование метрик между вкладками", "low", "Product", "Недочёты: дублирование"),
    ]

    victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name ILIKE $1 LIMIT 1", "Виктория")
    if not victoria_id:
        logger.warning("Expert Victoria not found, skipping dashboard tasks")
        return 0
    domain_id = await conn.fetchval("SELECT id FROM domains WHERE name ILIKE $1 LIMIT 1", "Dashboard")
    if not domain_id:
        await conn.execute(
            "INSERT INTO domains (name, description) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING",
            "Dashboard",
            "Dashboard improvements and analytics",
        )
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name ILIKE $1 LIMIT 1", "Dashboard")

    for title, priority, assignee_hint, description in checklist:
        full_title = f"📊 Дашборд: {title}"
        # Избегаем дублирования: не создаём если такая задача уже есть за последние 24ч
        existing = await conn.fetchval("""
            SELECT 1 FROM tasks
            WHERE title = $1 AND created_at > NOW() - INTERVAL '24 hours'
            LIMIT 1
        """, full_title)
        if existing:
            continue
        metadata = json.dumps({"source": "dashboard_daily_improver", "assignee_hint": assignee_hint})
        await conn.execute("""
            INSERT INTO tasks (title, description, status, priority, creator_expert_id, domain_id, metadata)
            VALUES ($1, $2, 'pending', $3, $4, $5, $6::jsonb)
        """, full_title, description, priority, victoria_id, domain_id, metadata)
        tasks_created += 1

    return tasks_created


async def _log_improvement_to_knowledge(conn, summary: str) -> bool:
    """Сохраняет лог цикла улучшений в knowledge_nodes (domain: Dashboard)."""
    try:
        domain_id = await conn.fetchval("SELECT id FROM domains WHERE name ILIKE $1 LIMIT 1", "Dashboard")
        if not domain_id:
            return False
        metadata = json.dumps({"source": "dashboard_daily_improver", "cycle": datetime.now().isoformat()})
        await conn.execute("""
            INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
            VALUES ($1, $2, $3::jsonb, 0.8, 'dashboard_improvement_cycle')
        """, domain_id, summary[:2000], metadata)
        return True
    except Exception as e:
        logger.warning("Could not log to knowledge_nodes: %s", e)
        return False


async def run_dashboard_improvement_cycle() -> Dict[str, Any]:
    """
    Запускает цикл ежедневного улучшения дашборда.
    Создаёт задачи в tasks и логирует в knowledge_nodes.
    """
    try:
        import asyncpg
    except ImportError:
        logger.warning("asyncpg not available for dashboard_daily_improver")
        return {"tasks_created": 0, "logged": False}

    try:
        conn = await asyncpg.connect(_DB_URL)
        try:
            tasks_created = await _create_dashboard_improvement_tasks(conn)
            summary = f"Dashboard improvement cycle: {tasks_created} tasks created at {datetime.now().isoformat()}"
            logged = await _log_improvement_to_knowledge(conn, summary)
            logger.info("[DASHBOARD_IMPROVER] %s", summary)
            return {"tasks_created": tasks_created, "logged": logged}
        finally:
            await conn.close()
    except Exception as e:
        logger.error("dashboard_daily_improver failed: %s", e, exc_info=True)
        return {"tasks_created": 0, "logged": False}
