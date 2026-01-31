#!/usr/bin/env python3
"""
Простой скрипт для назначения задач экспертам
Запуск: python3 scripts/assign_tasks_to_experts.py
"""
import asyncio
import asyncpg
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:secret@localhost:5432/knowledge_os"
)

async def assign_tasks():
    """Назначает задачи экспертам"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Получаем количество неназначенных задач
        unassigned = await conn.fetchval("""
            SELECT COUNT(*) FROM tasks 
            WHERE assignee_expert_id IS NULL 
            AND status = 'pending'
        """)
        print(f"📋 Неназначенных задач: {unassigned}")
        
        if unassigned == 0:
            print("✅ Все задачи уже назначены")
            return
        
        # Назначаем задачи экспертам (максимум 1000 за раз)
        result = await conn.execute("""
            UPDATE tasks t
            SET assignee_expert_id = (
                SELECT e.id 
                FROM experts e 
                WHERE e.id NOT IN (
                    SELECT DISTINCT assignee_expert_id 
                    FROM tasks 
                    WHERE status IN ('pending', 'in_progress') 
                    AND assignee_expert_id IS NOT NULL
                    GROUP BY assignee_expert_id 
                    HAVING COUNT(*) > 10
                )
                ORDER BY RANDOM()
                LIMIT 1
            )
            WHERE t.assignee_expert_id IS NULL 
            AND t.status = 'pending'
            AND EXISTS (SELECT 1 FROM experts LIMIT 1)
            LIMIT 1000
        """)
        
        print(f"✅ Назначено задач: {result.split()[-1] if result else '0'}")
        
        # Проверяем результат
        assigned = await conn.fetchval("""
            SELECT COUNT(*) FROM tasks 
            WHERE assignee_expert_id IS NOT NULL 
            AND status = 'pending'
        """)
        print(f"📊 Всего назначенных задач: {assigned}")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(assign_tasks())
