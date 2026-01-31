import asyncio
import os
import asyncpg

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

async def apply_cache_migration():
    try:
        conn = await asyncpg.connect(DB_URL)
        with open('/Users/zhuchyok/Documents/GITHUB/atra/atra/knowledge_os/db/migrations/add_semantic_cache.sql', 'r') as f:
            await conn.execute(f.read())
        await conn.close()
        print("✅ Semantic Cache Migration applied manually.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(apply_cache_migration())

