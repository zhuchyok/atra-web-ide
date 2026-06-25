import asyncpg
import asyncio
import os
import json

async def check():
    pool = await asyncpg.create_pool(os.getenv('DATABASE_URL'))
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, status, metadata FROM tasks ORDER BY updated_at DESC LIMIT 20")
        for r in rows:
            meta = r['metadata']
            if isinstance(meta, str):
                meta = json.loads(meta)
            print(f"ID: {r['id']} | Status: {r['status']}")
            print(f"Metadata: {json.dumps(meta, indent=2, ensure_ascii=False)}")
            print("-" * 20)
    await pool.close()

if __name__ == "__main__":
    asyncio.run(check())
