import asyncpg
import asyncio
import os

async def main():
    db_url = "postgresql://admin:secret@localhost:5432/knowledge_os"
    conn = await asyncpg.connect(db_url)
    rows = await conn.fetch("SELECT id, status, title, created_at FROM tasks ORDER BY created_at DESC LIMIT 10")
    for r in rows:
        print(f"ID: {r[0]}, Status: {r[1]}, Title: {r[2]}, Created: {r[3]}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
