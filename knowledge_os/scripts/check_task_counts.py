import asyncio
import os

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


async def get_task_counts():
    conn = await asyncpg.connect(DB_URL)
    try:
        rows = await conn.fetch("SELECT status, count(*) FROM tasks GROUP BY status;")
        for row in rows:
            print(f"{row['status']}: {row['count']}")

        # Also check for tasks that have been in_progress for too long (> 1 hour)
        zombies = await conn.fetch(
            "SELECT id, title, updated_at FROM tasks WHERE status = 'in_progress' AND updated_at < NOW() - INTERVAL '1 hour';"
        )
        if zombies:
            print("\nZombie tasks (in_progress for > 1 hour):")
            for z in zombies:
                print(f"ID: {z['id']} | Title: {z['title']} | Last Updated: {z['updated_at']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(get_task_counts())
