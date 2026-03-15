import asyncio
import os
import asyncpg

async def migrate_tasks_table():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        # Check if embedding column already exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tasks' AND column_name = 'embedding'
            )
        """)

        if not exists:
            print("Adding 'embedding' column to 'tasks' table...")
            # We use vector(768) for nomic-embed-text
            await conn.execute("ALTER TABLE tasks ADD COLUMN embedding vector(768)")
            print("Column 'embedding' added successfully.")

            # Create index for fast semantic search
            print("Creating HNSW index on 'tasks.embedding'...")
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_embedding
                ON tasks USING hnsw (embedding vector_cosine_ops)
            """)
            print("Index created successfully.")
        else:
            print("Column 'embedding' already exists in 'tasks' table.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(migrate_tasks_table())
