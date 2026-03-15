import asyncio
import os
import asyncpg

async def inspect_tasks_table():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'tasks'
        """)
        print("Columns in 'tasks' table:")
        for col in columns:
            print(f" - {col['column_name']}: {col['data_type']}")

        # Check for vector extension and index
        has_vector = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        print(f"\npgvector extension exists: {has_vector}")

        if has_vector:
            indexes = await conn.fetch("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'tasks'
            """)
            print("\nIndexes on 'tasks' table:")
            for idx in indexes:
                print(f" - {idx['indexname']}: {idx['indexdef']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect_tasks_table())
