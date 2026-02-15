"""
Контекст последних завершённых задач для understand_goal (план «умнее быстрее» §2.1).
При фразах «как вчера», «как с X», «повтори» подставляется перед understand_goal,
чтобы LLM мог переформулировать цель с опорой на недавние задачи.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Маркеры отсылки к прошлому (план §2.1)
AMBIGUOUS_GOAL_MARKERS = (
    "как вчера",
    "как тогда",
    "как с ",
    "повтори",
    "то же что",
    "то же самое",
)


def is_ambiguous_goal_reference(goal: str) -> bool:
    """Проверить, отсылается ли запрос к предыдущему действию («как вчера», «повтори» и т.п.)."""
    if not goal or not isinstance(goal, str):
        return False
    g = goal.strip().lower()
    return any(m in g for m in AMBIGUOUS_GOAL_MARKERS)


async def get_recent_completed_tasks_context(
    project_context: Optional[str] = None,
    limit: int = 5,
    max_chars: int = 800,
) -> str:
    """
    Получить текст «последние завершённые задачи» для подстановки в промпт understand_goal.
    По project_context фильтруем задачи проекта; при None — последние по БД (все проекты).
    """
    try:
        import asyncpg
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return ""
        conn = await asyncpg.connect(db_url)
        try:
            if project_context and project_context.strip():
                # Колонка project_context может отсутствовать до миграции — используем безопасный запрос
                try:
                    rows = await conn.fetch(
                        """SELECT title, updated_at
                           FROM tasks
                           WHERE status = 'completed' AND project_context = $1
                           ORDER BY updated_at DESC NULLS LAST
                           LIMIT $2""",
                        project_context.strip(),
                        limit,
                    )
                except asyncpg.UndefinedColumnError:
                    rows = await conn.fetch(
                        """SELECT title, updated_at
                           FROM tasks
                           WHERE status = 'completed'
                           ORDER BY updated_at DESC NULLS LAST
                           LIMIT $2""",
                        limit,
                    )
            else:
                rows = await conn.fetch(
                    """SELECT title, updated_at
                       FROM tasks
                       WHERE status = 'completed'
                       ORDER BY updated_at DESC NULLS LAST
                       LIMIT $1""",
                    limit,
                )
            if not rows:
                return ""
            parts = []
            for r in rows:
                title = (r.get("title") or "")[:100]
                updated = r.get("updated_at")
                updated_str = (
                    updated.strftime("%d.%m %H:%M")
                    if hasattr(updated, "strftime")
                    else (str(updated)[:16] if updated else "")
                )
                parts.append(f"- {title} ({updated_str})")
            out = "Пользователь отсылает к предыдущему действию. Контекст последних завершённых задач:\n" + "\n".join(parts)
            return out[:max_chars]
        finally:
            await conn.close()
    except Exception as e:
        logger.debug("get_recent_completed_tasks_context: %s", e)
    return ""
