import asyncio
import json
import os
import subprocess
from datetime import datetime

import asyncpg
from ai_core import run_smart_agent_sync

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")


def run_cursor_agent(prompt: str, expert_name: str = "Глеб"):
    return run_smart_agent_sync(prompt, expert_name=expert_name, category="expert_task")


async def process_task_for_expert(expert_name):
    print(f"🧠 {expert_name} приступает к выполнению задачи...")
    conn = await asyncpg.connect(DB_URL)
    try:
        from app.expert_aliases import resolve_expert_name_for_db

        resolved_name = resolve_expert_name_for_db(expert_name)
    except ImportError:
        resolved_name = expert_name
    # 1. Получаем конфиг эксперта
    expert = await conn.fetchrow(
        "SELECT id, name, system_prompt, role, department FROM experts WHERE name = $1",
        resolved_name,
    )
    if not expert:
        print(f"❌ Эксперт {expert_name} не найден.")
        return

    # 2. Ищем задачу
    task_row = await conn.fetchrow(
        """
        SELECT id, title, description, metadata
        FROM tasks
        WHERE assignee_expert_id = $1 AND status = 'pending'
        ORDER BY created_at ASC LIMIT 1
    """,
        expert["id"],
    )

    if not task_row:
        print(f"✅ У эксперта {expert_name} нет активных задач.")
        await conn.close()
        return

    task = dict(task_row)
    if isinstance(task["metadata"], str):
        task["metadata"] = json.loads(task["metadata"])

    # 3. Собираем контекст (релевантные знания)
    business_target = task["metadata"].get("business", "Столичные окна")
    context_nodes = await conn.fetch(
        """
        SELECT content FROM knowledge_nodes
        WHERE metadata->>'source' = 'scout_research'
        AND metadata->>'business_target' = $1
        ORDER BY created_at DESC
        LIMIT 150
    """,
        business_target,
    )

    context_text = "\n".join([n["content"] for n in context_nodes])

    # 4. Формируем промпт
    prompt = f"""
    {expert["system_prompt"]}

    ЗАДАЧА: {task["title"]}
    ИНСТРУКЦИЯ: {task["description"]}

    СОБРАННЫЕ ДАННЫЕ ДЛЯ АНАЛИЗА:
    {context_text}

    ТВОЯ ЦЕЛЬ: Сделай глубокий анализ рынка.
    1. Назови топ-10 реальных конкурентов в Чебоксарах/Новочебоксарске.
    2. Опиши их сильные стороны.
    3. Какие боли клиентов они НЕ закрывают (из отзывов)?
    4. Что делать 'Столичным окнам' чтобы забрать долю рынка?
    """

    report = run_cursor_agent(prompt, expert_name=expert["name"])

    if report:
        # 5. Сохраняем результат как верифицированное знание (по возможности с embedding — VERIFICATION §5)
        domain_id = await conn.fetchval(
            "SELECT id FROM domains WHERE name = $1", expert["department"]
        )
        content_kn = f"📊 ОТЧЕТ РАЗВЕДКИ: {task['title']}\n\n{report}"
        meta_kn = json.dumps(
            {
                "source": "expert_task_report",
                "expert_id": str(expert["id"]),
                "expert_name": expert["name"],
                "task_id": str(task["id"]),
            }
        )
        embedding = None
        try:
            from semantic_cache import get_embedding

            embedding = await get_embedding(content_kn[:8000])
        except Exception:
            pass
        if embedding is not None:
            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified, embedding)
                VALUES ($1, $2, 0.98, $3, TRUE, $4::vector)
            """,
                domain_id,
                content_kn,
                meta_kn,
                str(embedding),
            )
        else:
            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ($1, $2, 0.98, $3, TRUE)
            """,
                domain_id,
                content_kn,
                meta_kn,
            )

        # 6. Обновляем статус задачи
        await conn.execute("UPDATE tasks SET status = 'completed' WHERE id = $1", task["id"])

        # 7. Нотифицируем Викторияию
        await conn.execute(
            """
            INSERT INTO notifications (message)
            VALUES ($1)
        """,
            f"🕵️ Глеб завершил анализ конкурентов для '{task['metadata'].get('business')}'. Отчет готов.",
        )

        print(f"✅ {expert_name} успешно выполнил задачу и сохранил отчет.")
    else:
        print(f"❌ {expert_name} не смог сгенерировать отчет.")

    await conn.close()


if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "Глеб"
    asyncio.run(process_task_for_expert(name))
