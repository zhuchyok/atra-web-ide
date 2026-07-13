import asyncio
import os

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


async def fix_zombies():
    conn = await asyncpg.connect(DB_URL)
    try:
        res = await conn.execute(
            "UPDATE tasks SET status = 'pending' WHERE status = 'in_progress' AND updated_at < NOW() - INTERVAL '1 hour';"
        )
        print(f"Updated: {res}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(fix_zombies())
