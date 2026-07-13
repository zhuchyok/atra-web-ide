import asyncio
import logging
import os
from datetime import datetime, timedelta

import asyncpg

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("FailedTasksAnalyzer")

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os"
)


async def analyze_and_cleanup():
    """Анализирует проваленные задачи, группирует их и чистит дубли."""
    try:
        conn = await asyncpg.connect(DB_URL)

        logger.info("🔍 Starting Failed Tasks Analysis...")

        # 1. Группировка проваленных задач по тексту ошибки
        # Берем задачи за последние 24 часа
        failed_groups = await conn.fetch("""
            SELECT LEFT(result, 150) as error_pattern, count(*) as cnt,
                   array_agg(id::text) as task_ids,
                   min(title) as sample_title
            FROM tasks
            WHERE status = 'failed'
            AND updated_at > NOW() - INTERVAL '24 hours'
            GROUP BY error_pattern
            HAVING count(*) > 5
            ORDER BY cnt DESC
        """)

        if not failed_groups:
            logger.info("✅ No massive failure patterns detected.")
        else:
            for group in failed_groups:
                pattern = group["error_pattern"]
                count = group["cnt"]
                sample_title = group["sample_title"]

                logger.warning(f"🚨 Pattern detected: '{pattern[:100]}...' occurs {count} times.")

                # Если это таймаут, создаем одну агрегированную задачу для анализа
                if "timed out" in pattern.lower() or "Circuit Breaker" in pattern:
                    analysis_goal = f"SYSTEM AUDIT: {count} tasks failed with timeout. Sample: {sample_title}. Check MLX/Ollama load and RAM usage."

                    # Проверяем, нет ли уже такой задачи
                    exists = await conn.fetchval(
                        "SELECT count(*) FROM tasks WHERE title = $1 AND status IN ('pending', 'in_progress')",
                        "🚨 SYSTEM AUDIT: Timeout Storm",
                    )

                    if not exists:
                        await conn.execute(
                            """
                            INSERT INTO tasks (title, description, status, priority, metadata)
                            VALUES ($1, $2, 'pending', 'high', $3)
                        """,
                            "🚨 SYSTEM AUDIT: Timeout Storm",
                            analysis_goal,
                            '{"source": "failed_tasks_analyzer", "auto_generated": true}',
                        )
                        logger.info("➕ Created System Audit task for Igor.")

                # 2. Удаляем дубликаты в этой группе, оставляя только 1 (для истории)
                ids_to_delete = group["task_ids"][1:]
                if ids_to_delete:
                    import uuid

                    await conn.execute(
                        "DELETE FROM tasks WHERE id = ANY($1::uuid[])",
                        [uuid.UUID(i) for i in ids_to_delete],
                    )
                    logger.info(f"🗑️ Cleaned up {len(ids_to_delete)} duplicate failed tasks.")

        # 3. Общая статистика для отчета
        stats = await conn.fetchrow(
            "SELECT count(*) as total, count(*) FILTER (WHERE status = 'failed') as failed FROM tasks"
        )
        logger.info(f"📊 Current DB State: Total={stats['total']}, Failed={stats['failed']}")

        await conn.close()
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")


if __name__ == "__main__":
    asyncio.run(analyze_and_cleanup())
