import asyncpg
import asyncio
import os

async def check():
    pool = await asyncpg.create_pool(os.getenv('DATABASE_URL'))
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, expert_name FROM tasks WHERE status = 'in_progress'")
        for r in rows:
            print(f"ID: {r['id']} | Expert: {r['expert_name']}")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(check())
