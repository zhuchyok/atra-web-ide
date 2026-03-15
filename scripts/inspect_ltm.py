import asyncio
import os
import asyncpg

async def inspect_ltm():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'long_term_memory'
        """)
        print("Columns in 'long_term_memory' table:")
        for col in columns:
            print(f" - {col['column_name']}: {col['data_type']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect_ltm())
