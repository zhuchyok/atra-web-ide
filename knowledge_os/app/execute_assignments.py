"""
Исполнение по назначениям оркестратора (план «как я» п.12.2 п.1).

При наличии assignments от IntegrationBridge вызываем run_smart_agent по каждому эксперту,
собираем ответы и возвращаем агрегированный текст для подстановки в контекст Victoria.
Включается через EXECUTE_ASSIGNMENTS_IN_RUN=true в bridge (victoria_server).
"""

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _is_veronica_only(assignments: dict[str, Any]) -> bool:
    """Проверяет, что в назначениях только Veronica (тогда исполнение через делегирование)."""
    if not assignments or not isinstance(assignments, dict):
        return True
    for _k, v in assignments.items():
        if not isinstance(v, dict):
            continue
        name = (v.get("expert_name") or v.get("expert_id") or "").lower()
        if "veronica" not in name and "вероника" not in name:
            return False
    return True


# Для задач-аудита (аудит проекта и т.д.) — меньший таймаут на эксперта, чтобы не блокировать надолго
AUDIT_EXPERT_TIMEOUT = float(
    os.getenv("AUDIT_EXPERT_TIMEOUT", "300")
)  # 5 мин на эксперта при аудите


def _is_audit_goal(goal: str) -> bool:
    """Проверка: задача похожа на аудит (долгий анализ проекта)."""
    if not goal:
        return False
    g = goal.lower().strip()
    return "аудит" in g or " audit" in g or "audit " in g or g.startswith("audit")


async def execute_assignments_async(
    assignments: dict[str, Any],
    goal: str,
    strategy: str | None = None,
    project_context: str | None = None,
    timeout_per_expert: float = 600.0,  # Увеличили таймаут для "монстра" до 10 минут
) -> str:
    """
    Вызвать экспертов по плану оркестратора.
    МОНСТР-ЛОГИКА: Создает реальные задачи в БД tasks для отслеживания в дашборде.
    ОПТИМИЗАЦИЯ: Для аудитов (goal содержит "аудит") — меньший таймаут на эксперта (5 мин, не 10).
    """
    # Для аудитов (долгих задач) сокращаем таймаут на эксперта
    if _is_audit_goal(goal):
        timeout_per_expert = AUDIT_EXPERT_TIMEOUT
        logger.info(
            f"🔍 [AUDIT] Задача похожа на аудит, сокращаем таймаут на эксперта до {timeout_per_expert}с"
        )

    if not assignments or not isinstance(assignments, dict):
        return ""

    # Пытаемся подключиться к БД
    import json
    import os
    from datetime import datetime, timezone

    import asyncpg

    # Пытаемся импортировать redis_manager
    try:
        from app.redis_manager import redis_manager
    except ImportError:
        try:
            from redis_manager import redis_manager
        except ImportError:
            redis_manager = None

    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

    strategy_line = f"\nСтратегия оркестратора: {strategy}" if strategy else ""
    prompt_template = (
        "Задача от Team Lead Victoria: {goal}{strategy_line}\n\n"
        "Твоя роль: {expert_name}. Выполни свою часть работы и дай краткий отчет."
    )

    results = []

    try:
        conn = await asyncpg.connect(db_url, timeout=5)
        try:
            # Получаем ID Виктории
            victoria_id = await conn.fetchval(
                "SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1"
            )

            tasks_to_run = []
            task_info = []  # (key, expert_name, task_id, subtask_desc)

            for key, val in assignments.items():
                expert_name = val.get("expert_name") or val.get("expert_id") or key
                # File/security audits must not land on Marketing/etc. (wrong twin UX).
                goal_l = (goal or "").lower()
                is_file_audit = any(
                    p in goal_l
                    for p in (
                        "проверь файл",
                        "check file",
                        "pip install",
                        "hardcoded",
                        "секрет",
                        "subprocess",
                    )
                )
                if is_file_audit:
                    dept = await conn.fetchval(
                        "SELECT department FROM experts WHERE name = $1 LIMIT 1",
                        expert_name,
                    )
                    dept_l = (dept or "").lower()
                    if dept_l and not any(
                        x in dept_l
                        for x in ("backend", "security", "devops", "qa", "engineering", "tech")
                    ):
                        preferred = await conn.fetchval(
                            """
                            SELECT name FROM experts
                            WHERE name IN ('Алексей', 'Игорь', 'Анна', 'Сергей')
                            ORDER BY CASE name
                                WHEN 'Алексей' THEN 0
                                WHEN 'Игорь' THEN 1
                                WHEN 'Анна' THEN 2
                                ELSE 3
                            END
                            LIMIT 1
                            """
                        )
                        if preferred:
                            logger.info(
                                "🛡️ [MONSTER] Re-route file-audit %s → %s (was %s/%s)",
                                key,
                                preferred,
                                expert_name,
                                dept,
                            )
                            expert_name = preferred

                # Резолвим эксперта
                expert_id = await conn.fetchval(
                    "SELECT id FROM experts WHERE name = $1 LIMIT 1", expert_name
                )

                subtask_desc = prompt_template.format(
                    goal=goal[:1000],
                    strategy_line=strategy_line,
                    expert_name=expert_name,
                )

                # СОЗДАЕМ РЕАЛЬНУЮ ЗАДАЧУ В БД
                # ON CONFLICT: idx_tasks_active_dedup защищает от дублей (title+project_context, active only).
                # DO UPDATE SET updated_at=NOW() гарантирует RETURNING id даже при конфликте.
                task_title = f"🤖 Делегировано: {expert_name} ({key})"
                # Idempotent upsert pattern (Google SRE): UPDATE first → INSERT if no rows touched.
                # Avoids partial-index ON CONFLICT expression mismatch with COALESCE cast.
                task_id = await conn.fetchval(
                    """
                    UPDATE tasks SET updated_at = NOW()
                    WHERE title = $1
                      AND status IN ('pending', 'in_progress')
                      AND COALESCE(project_context, 'default') = 'default'
                    RETURNING id
                    """,
                    task_title,
                )
                if not task_id:
                    task_id = await conn.fetchval(
                        """
                        INSERT INTO tasks (title, description, status, priority, assignee_expert_id, creator_expert_id, metadata)
                        VALUES ($1, $2, 'pending', 'high', $3, $4, $5)
                        RETURNING id
                        """,
                        task_title,
                        subtask_desc,
                        expert_id,
                        victoria_id,
                        json.dumps(
                            {"source": "victoria_monster_delegation", "parent_goal": goal[:200]}
                        ),
                    )

                logger.info(f"🚀 [MONSTER] Создана/найдена задача {task_id} для {expert_name}")

                # МОНСТР-ЛОГИКА 10.0: Отправляем задачу в Redis Stream для асинхронного воркера
                if redis_manager:
                    await redis_manager.push_to_stream(
                        "expert_tasks",
                        {
                            "task_id": str(task_id),
                            "expert_name": expert_name,
                            "description": subtask_desc,
                            "category": "orchestrator_assignment",
                            "project_context": project_context,
                            "metadata": {
                                "complex": True
                            },  # Форсируем ReAct для выполнения действий (создание файлов и т.д.)
                        },
                    )
                    logger.info(f"📥 [MONSTER] Задача {task_id} отправлена в очередь Redis")
                    continue  # Workers handle processing, skip local execution

                task_info.append((key, expert_name, task_id, subtask_desc))

            # Теперь выполняем их ПАРАЛЛЕЛЬНО
            async def run_single_expert(key, expert_name, task_id, subtask_desc):
                # Каждому эксперту — своё соединение, чтобы не было InterfaceError
                expert_conn = await asyncpg.connect(db_url, timeout=5)
                try:
                    # Устанавливаем статус in_progress
                    await expert_conn.execute(
                        "UPDATE tasks SET status = 'in_progress' WHERE id = $1", task_id
                    )

                    try:
                        from app.ai_core import run_smart_agent_async
                    except ImportError:
                        from ai_core import run_smart_agent_async

                    max_retries = 3
                    retry_delay = 5  # Начальная задержка в секундах
                    last_error = None

                    for attempt in range(max_retries + 1):
                        try:
                            if attempt > 0:
                                logger.info(
                                    f"🔄 [SELF-HEALING] Попытка {attempt}/{max_retries} для {expert_name} (задержка {retry_delay}с)"
                                )
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2  # Экспоненциальная задержка

                            logger.info(
                                f"⏳ [MONSTER] Запуск run_smart_agent_async для {expert_name}, timeout={timeout_per_expert}"
                            )
                            # [SINGULARITY 24.3] Fix RecursionError in cancel()
                            # Use a non-recursive cancellation strategy if possible or wrap in try-except
                            # but the root cause is often deeply nested tasks in asyncio.wait_for
                            try:
                                report = await asyncio.wait_for(
                                    run_smart_agent_async(
                                        subtask_desc,
                                        expert_name=expert_name,
                                        category="orchestrator_assignment",
                                        project_context=project_context,
                                    ),
                                    timeout=timeout_per_expert,
                                )
                            except RecursionError:
                                logger.error(
                                    f"⚠️ [MONSTER] RecursionError detected during wait_for for {expert_name}. Attempting recovery."
                                )
                                # Fallback to a direct call without wait_for if recursion happens in asyncio internals
                                report = await run_smart_agent_async(
                                    subtask_desc,
                                    expert_name=expert_name,
                                    category="orchestrator_assignment",
                                    project_context=project_context,
                                )

                            # Если дошли сюда, значит успех
                            # Обновляем задачу в БД как завершенную
                            report_text = str(
                                report.get("result") if isinstance(report, dict) else report
                            )
                            await expert_conn.execute(
                                """
                                UPDATE tasks SET status = 'completed', result = $2, completed_at = NOW()
                                WHERE id = $1
                            """,
                                task_id,
                                report_text,
                            )

                            # МОНСТР-ЛОГИКА: Сохраняем результат в knowledge_nodes, чтобы эксперты учились друг у друга
                            try:
                                # Пытаемся получить эмбеддинг для RAG
                                embedding = None
                                try:
                                    from app.semantic_cache import get_embedding

                                    embedding = await get_embedding(report_text[:1000])
                                except Exception:
                                    pass

                                await expert_conn.execute(
                                    """
                                    INSERT INTO knowledge_nodes (content, domain_id, confidence_score, embedding, is_verified, metadata)
                                    VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.9, $2, TRUE, $3::jsonb)
                                    ON CONFLICT DO NOTHING
                                """,
                                    report_text[:2000],
                                    embedding,
                                    json.dumps(
                                        {
                                            "source": "expert_subtask",
                                            "expert": expert_name,
                                            "task_id": str(task_id),
                                            "parent_goal": goal[:200],
                                            "timestamp": datetime.now(timezone.utc).isoformat(),
                                        }
                                    ),
                                )
                                logger.info(
                                    f"📚 [LEARNING] Знание от {expert_name} сохранено в базу знаний"
                                )
                            except Exception as le:
                                logger.warning(
                                    f"⚠️ [LEARNING] Не удалось сохранить знание от {expert_name}: {le}"
                                )

                            return (key, expert_name, report_text[:800])

                        except Exception as e:
                            last_error = e
                            logger.error(
                                f"❌ [MONSTER] Ошибка в попытке {attempt} для {expert_name}: {e}"
                            )
                            if attempt == max_retries:
                                raise e

                except Exception as e:
                    import traceback

                    error_msg = f"FATAL EXCEPTION after retries: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                    logger.error(
                        f"💀 [MONSTER] Фатальная ошибка выполнения для {expert_name}: {error_msg}"
                    )
                    await expert_conn.execute(
                        "UPDATE tasks SET status = 'failed', result = $2 WHERE id = $1",
                        task_id,
                        error_msg,
                    )
                    return (key, expert_name, f"(фатальная ошибка: {e})")
                finally:
                    await expert_conn.close()

            # Запускаем все задачи одновременно
            tasks_to_run = [run_single_expert(*info) for info in task_info]
            results_list = await asyncio.gather(*tasks_to_run)
            results.extend(results_list)

        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Monster delegation failed: {e}")
        # Fallback на старую логику без БД если база лежит
        return "Ошибка делегирования через БД. Проверьте подключение."

    parts = ["Результаты работы команды экспертов:"]
    for key, name, text in results:
        parts.append(f"\n• {key} ({name}): {text}")

    return "\n".join(parts) if len(results) > 0 else ""
