import asyncio
import os
import asyncpg

async def count_tasks():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        count = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE embedding IS NULL AND status = 'completed'")
        print(f"Tasks without embeddings (completed): {count}")

        all_count = await conn.fetchval("SELECT COUNT(*) FROM tasks")
        print(f"Total tasks: {all_count}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(count_tasks())
