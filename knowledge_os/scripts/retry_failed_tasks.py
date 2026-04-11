import asyncio
import asyncpg
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RetryTasks")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

async def retry_failed_tasks(limit: int = 15):
    try:
        conn = await asyncpg.connect(DB_URL)
        
        # Находим задачи с таймаутами или ошибками связи
        tasks = await conn.fetch("""
            SELECT id, title, result
            FROM tasks
            WHERE status = 'failed'
            AND (result ILIKE '%timeout%' OR result ILIKE '%Connect call failed%' OR result ILIKE '%Circuit Breaker%')
            ORDER BY updated_at DESC
            LIMIT $1
        """, limit)
        
        if not tasks:
            logger.info("✅ No tasks matching retry criteria found.")
            await conn.close()
            return

        for task in tasks:
            logger.info(f"🔄 [RETRY] Rescheduling task {task['id']}: {task['title']}")
            # Сбрасываем статус в pending
            await conn.execute("""
                UPDATE tasks 
                SET status = 'pending', result = NULL, updated_at = NOW()
                WHERE id = $1
            """, task['id'])
        
        logger.info(f"🚀 Successfully rescheduled {len(tasks)} tasks.")
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Retry failed: {e}")

if __name__ == "__main__":
    asyncio.run(retry_failed_tasks())
