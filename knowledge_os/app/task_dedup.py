# -*- coding: utf-8 -*-
"""
Дедупликация задач, создаваемых из обучения (оркестратор, curiosity engine).

Правило: одна и та же задача (title + description) для одного и того же эксперта
не создаётся чаще одного раза за период (по умолчанию 30 дней).
Учитываются все статусы (pending, in_progress, completed), чтобы не дублировать
назначение одному эксперту.

Используется в:
- Enhanced Orchestrator Phase 5 (Curiosity Engine)
- Streaming Orchestrator (_run_curiosity_engine)
"""
import logging
logger = logging.getLogger(__name__)


async def same_task_for_expert_in_last_n_days(
    conn,
    title: str,
    description: str,
    assignee_expert_id,
    days: int = 30
) -> bool:
    """
    Проверяет, была ли уже такая же задача у этого эксперта за последние N дней.

    Критерий «та же задача»: совпадение нормализованных title и description
    и тот же assignee_expert_id. Учитываются все статусы задач.

    Args:
        conn: asyncpg connection (из pool.acquire() или переданное соединение).
        title: заголовок задачи (будет нормализован через strip).
        description: описание задачи (будет нормализован через strip).
        assignee_expert_id: UUID эксперта (назначенного или планируемого).
        days: окно в днях (по умолчанию 30 = «не чаще раза в месяц»).

    Returns:
        True — дубликат есть, создавать задачу не нужно.
        False — дубликата нет, можно создавать.
    """
    if not assignee_expert_id:
        return False
    title_norm = (title or "").strip()
    description_norm = (description or "").strip()
    if not title_norm or not description_norm:
        return False
    try:
        exists = await conn.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM tasks t
                WHERE t.title = $1
                  AND t.description = $2
                  AND t.assignee_expert_id = $3
                  AND t.created_at >= NOW() - ($4 || ' days')::interval
            )
        """, title_norm, description_norm, assignee_expert_id, str(days))
        return bool(exists)
    except Exception as e:
        logger.warning("Task dedup check failed: %s", e)
        return False
