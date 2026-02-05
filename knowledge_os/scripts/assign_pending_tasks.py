#!/usr/bin/env python3
"""
Разовое назначение экспертов всем pending-задачам без assignee (Фаза 2 оркестратора).
После запуска Smart Worker подхватит уже назначенные задачи.

Запуск из корня репо:
  cd knowledge_os && .venv/bin/python scripts/assign_pending_tasks.py

Требуется: DATABASE_URL (или по умолчанию postgresql://admin:secret@localhost:5432/knowledge_os).
"""
import asyncio
import os
import sys

# app в пути для импорта knowledge_os.app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

async def main():
    from app.db_pool import get_pool
    from app.enhanced_orchestrator import assign_task_to_best_expert

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            # Статистика
            total_pending = await conn.fetchval(
                "SELECT COUNT(*) FROM tasks WHERE status = 'pending'"
            )
            unassigned = await conn.fetchval(
                """SELECT COUNT(*) FROM tasks 
                   WHERE assignee_expert_id IS NULL AND status = 'pending'"""
            )
            assigned_pending = (total_pending or 0) - (unassigned or 0)
            print(f"[assign_pending_tasks] Pending всего: {total_pending}")
            print(f"  без исполнителя (назначим): {unassigned}")
            print(f"  уже с исполнителем (забрал воркер): {assigned_pending}")

            if not unassigned:
                print("Нечего назначать. Запустите Smart Worker для обработки очереди.")
                return 0

            # Выбираем только не назначенные, без decomposed
            tasks = await conn.fetch("""
                SELECT id, title, domain_id, metadata
                FROM tasks
                WHERE assignee_expert_id IS NULL
                AND status = 'pending'
                AND (metadata->>'decomposed') IS DISTINCT FROM 'true'
                ORDER BY
                    CASE priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    created_at ASC
            """)
            n = 0
            for task in tasks:
                try:
                    meta = task.get("metadata")
                    if isinstance(meta, str):
                        import json
                        meta = json.loads(meta) if meta else {}
                    elif meta is None:
                        meta = {}
                    await assign_task_to_best_expert(
                        conn, str(task["id"]), task.get("domain_id"), metadata=meta
                    )
                    n += 1
                except Exception as e:
                    print(f"  ⚠ Задача {task['id']}: {e}")
            print(f"[assign_pending_tasks] Назначено: {n} задач.")
            print("Дальше: убедитесь, что Smart Worker запущен (knowledge_os_worker).")
    finally:
        await pool.close()
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
