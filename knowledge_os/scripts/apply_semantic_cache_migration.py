import asyncio
import os
import asyncpg

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
MIGRATION_PATH = "/Users/zhuchyok/Documents/GITHUB/atra/atra/knowledge_os/db/migrations/add_semantic_cache.sql"

async def apply_migration():
    print(f"Applying migration from {MIGRATION_PATH}...")
    try:
        with open(MIGRATION_PATH, 'r') as f:
            sql = f.read()
            
        conn = await asyncpg.connect(DB_URL)
        await conn.execute(sql)
        await conn.close()
        print("✅ Migration applied successfully.")
    except Exception as e:
        print(f"❌ Error applying migration: {e}")

if __name__ == "__main__":
    asyncio.run(apply_migration())

