import asyncio
import asyncpg
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def check_schema():
    conn = await asyncpg.connect(DB_URL)

    for table in ['tasks', 'knowledge_nodes', 'session_context']:
        print(f"\n--- Schema for {table} ---")
        columns = await conn.fetch(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = '{table}'
        """)
        for c in columns:
            print(f"{c['column_name']}: {c['data_type']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_schema())
