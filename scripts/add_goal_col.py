import asyncio
import os
import asyncpg

async def add_goal_column():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'tasks' AND column_name = 'goal'
            )
        """)

        if not exists:
            print("Adding 'goal' column to 'tasks' table...")
            await conn.execute("ALTER TABLE tasks ADD COLUMN goal text")
            print("Column 'goal' added successfully.")
        else:
            print("Column 'goal' already exists.")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_goal_column())
