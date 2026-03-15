import asyncio
import os
import asyncpg

async def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    rows = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'tasks'")
    for r in rows:
        print(r['column_name'])
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
