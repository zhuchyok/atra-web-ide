import asyncio
import os

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


async def get_recent_pending():
    conn = await asyncpg.connect(DB_URL)
    try:
        rows = await conn.fetch(
            "SELECT id, title, created_at, status, updated_at FROM tasks WHERE status IN ('pending', 'in_progress') ORDER BY updated_at DESC;"
        )
        for r in rows:
            print(
                f"ID: {r['id']} | Status: {r['status']} | Created: {r['created_at']} | Title: {r['title']}"
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(get_recent_pending())
