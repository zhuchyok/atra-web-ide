import asyncio
import os
import asyncpg

async def list_tables():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        tables = await conn.fetch("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        print("Tables in database:")
        for t in tables:
            print(f" - {t['table_name']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(list_tables())
