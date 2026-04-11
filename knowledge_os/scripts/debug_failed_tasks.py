import asyncio
import asyncpg
import os
import json

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

async def get_failed_tasks():
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("""
        SELECT id, title, status, result, updated_at 
        FROM tasks 
        WHERE status = 'failed' 
        ORDER BY updated_at DESC 
        LIMIT 20
    """)
    for row in rows:
        print(f"ID: {row['id']}")
        print(f"Title: {row['title']}")
        print(f"Error: {row['result'][:200]}")
        print("-" * 40)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(get_failed_tasks())
