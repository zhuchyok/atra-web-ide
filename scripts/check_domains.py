import asyncio
import asyncpg
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def check_domains():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("SELECT id, name FROM domains")
    for r in rows:
        print(f"ID: {r['id']} | Name: {r['name']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_domains())
