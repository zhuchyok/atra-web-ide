"""
Исполнение по назначениям оркестратора (план «как я» п.12.2 п.1).

При наличии assignments от IntegrationBridge вызываем run_smart_agent по каждому эксперту,
собираем ответы и возвращаем агрегированный текст для подстановки в контекст Victoria.
Включается через EXECUTE_ASSIGNMENTS_IN_RUN=true в bridge (victoria_server).
"""

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _is_veronica_only(assignments: Dict[str, Any]) -> bool:
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


async def execute_assignments_async(
    assignments: Dict[str, Any],
    goal: str,
    strategy: Optional[str] = None,
    project_context: Optional[str] = None,
    timeout_per_expert: float = 600.0,  # Увеличили таймаут для "монстра" до 10 минут
) -> str:
    """
    Вызвать экспертов по плану оркестратора. 
    МОНСТР-ЛОГИКА: Создает реальные задачи в БД tasks для отслеживания в дашборде.
    """
    if not assignments or not isinstance(assignments, dict):
        return ""
    
    # Пытаемся подключиться к БД
    import os
    import asyncpg
    import json
    from datetime import datetime, timezone
    
    # Пытаемся импортировать redis_manager
    try:
        from app.redis_manager import redis_manager
    except ImportError:
        try:
            from redis_manager import redis_manager
        except ImportError:
            redis_manager = None
            
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    
    strategy_line = f"\nСтратегия оркестратора: {strategy}" if strategy else ""
    prompt_template = (
        "Задача от Team Lead Victoria: {goal}{strategy_line}\n\n"
        "Твоя роль: {expert_name}. Выполни свою часть работы и дай краткий отчет."
    )

    results = []
    
    try:
        conn = await asyncpg.connect(db_url, timeout=5.0)
        try:
            # Получаем ID Виктории
            victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1")
            
            tasks_to_run = []
            task_info = [] # (key, expert_name, task_id, subtask_desc)
            
            for key, val in assignments.items():
                expert_name = (val.get("expert_name") or val.get("expert_id") or key)
                # Резолвим эксперта
                expert_id = await conn.fetchval("SELECT id FROM experts WHERE name = $1 LIMIT 1", expert_name)
                
                subtask_desc = prompt_template.format(
                    goal=goal[:1000],
                    strategy_line=strategy_line,
                    expert_name=expert_name,
                )
                
                # СОЗДАЕМ РЕАЛЬНУЮ ЗАДАЧУ В БД
                task_id = await conn.fetchval("""
                    INSERT INTO tasks (title, description, status, priority, assignee_expert_id, creator_expert_id, metadata)
                    VALUES ($1, $2, 'pending', 'high', $3, $4, $5)
                    RETURNING id
                """, f"🤖 Делегировано: {expert_name} ({key})", subtask_desc, expert_id, victoria_id, 
                json.dumps({"source": "victoria_monster_delegation", "parent_goal": goal[:200]}))
                
                logger.info(f"🚀 [MONSTER] Создана задача {task_id} для {expert_name}")
                
                # МОНСТР-ЛОГИКА 10.0: Отправляем задачу в Redis Stream для асинхронного воркера
                if redis_manager:
                    await redis_manager.push_to_stream("expert_tasks", {
                        "task_id": str(task_id),
                        "expert_name": expert_name,
                        "description": subtask_desc,
                        "category": "orchestrator_assignment",
                        "project_context": project_context,
                        "metadata": {"complex": True} # Форсируем ReAct для выполнения действий (создание файлов и т.д.)
                    })
                    logger.info(f"📥 [MONSTER] Задача {task_id} отправлена в очередь Redis")
                    # Временно продолжаем выполнять здесь же для обратной совместимости, 
                    # пока не поднимем отдельный Worker Service
                
                task_info.append((key, expert_name, task_id, subtask_desc))

            # Теперь выполняем их ПАРАЛЛЕЛЬНО
            async def run_single_expert(key, expert_name, task_id, subtask_desc):
                # Каждому эксперту — своё соединение, чтобы не было InterfaceError
                expert_conn = await asyncpg.connect(db_url, timeout=5.0)
                try:
                    # Устанавливаем статус in_progress
                    await expert_conn.execute("UPDATE tasks SET status = 'in_progress' WHERE id = $1", task_id)
                    
                    try:
                        from app.ai_core import run_smart_agent_async
                    except ImportError:
                        from ai_core import run_smart_agent_async
                    
                    logger.info(f"⏳ [MONSTER] Запуск run_smart_agent_async для {expert_name}, timeout={timeout_per_expert}")
                    report = await asyncio.wait_for(
                        run_smart_agent_async(subtask_desc, expert_name=expert_name, category="orchestrator_assignment"),
                        timeout=timeout_per_expert
                    )
                    
                    # Обновляем задачу в БД как завершенную
                    report_text = str(report.get("result") if isinstance(report, dict) else report)
                    await expert_conn.execute("""
                        UPDATE tasks SET status = 'completed', result = $2, completed_at = NOW()
                        WHERE id = $1
                    """, task_id, report_text)
                    
                    # МОНСТР-ЛОГИКА: Сохраняем результат в knowledge_nodes, чтобы эксперты учились друг у друга
                    try:
                        # Пытаемся получить эмбеддинг для RAG
                        embedding = None
                        try:
                            from app.semantic_cache import get_embedding
                            embedding = await get_embedding(report_text[:1000])
                        except Exception:
                            pass

                        await expert_conn.execute("""
                            INSERT INTO knowledge_nodes (content, domain_id, confidence_score, embedding, is_verified, metadata)
                            VALUES ($1, (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1), 0.9, $2, TRUE, $3::jsonb)
                            ON CONFLICT DO NOTHING
                        """, report_text[:2000], embedding, json.dumps({
                            "source": "expert_subtask",
                            "expert": expert_name,
                            "task_id": str(task_id),
                            "parent_goal": goal[:200],
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }))
                        logger.info(f"📚 [LEARNING] Знание от {expert_name} сохранено в базу знаний")
                    except Exception as le:
                        logger.warning(f"⚠️ [LEARNING] Не удалось сохранить знание от {expert_name}: {le}")

                    return (key, expert_name, report_text[:800])
                except Exception as e:
                    import traceback
                    error_msg = f"EXCEPTION: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
                    logger.error(f"❌ [MONSTER] Ошибка выполнения для {expert_name}: {error_msg}")
                    await expert_conn.execute("UPDATE tasks SET status = 'failed', result = $2 WHERE id = $1", task_id, error_msg)
                    return (key, expert_name, f"(ошибка: {e})")
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
