import asyncio
import os
import asyncpg

async def check_embedding_column():
    db_url = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
    conn = await asyncpg.connect(db_url)
    try:
        # Try to select embedding from tasks
        try:
            val = await conn.fetchval("SELECT embedding FROM tasks LIMIT 1")
            print("Column 'embedding' exists in 'tasks' table.")
        except Exception as e:
            print(f"Column 'embedding' does NOT exist in 'tasks' table: {e}")

        # Check knowledge_nodes too
        try:
            val = await conn.fetchval("SELECT embedding FROM knowledge_nodes LIMIT 1")
            print("Column 'embedding' exists in 'knowledge_nodes' table.")
        except Exception as e:
            print(f"Column 'embedding' does NOT exist in 'knowledge_nodes' table: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_embedding_column())
