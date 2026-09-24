import asyncio
import os

import asyncpg

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


async def force_reset():
    conn = await asyncpg.connect(DB_URL)
    try:
        res = await conn.execute(
            "UPDATE tasks SET status = 'pending' WHERE id = 'f8593ae6-88a8-408d-a260-9505f0b35c4b';"
        )
        print(f"Updated: {res}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(force_reset())
