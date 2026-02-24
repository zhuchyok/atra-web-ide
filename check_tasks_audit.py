import asyncpg
import asyncio
import os

async def main():
    db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
    conn = await asyncpg.connect(db_url)

    # Check completed tasks
    completed = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
    print(f"Completed tasks: {completed}")

    # Check audited tasks
    audited = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE metadata->>'audited_by_victoria' = 'true'")
    print(f"Audited tasks: {audited}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
