import asyncio
import os
import asyncpg

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

async def fix_logs():
    try:
        conn = await asyncpg.connect(DB_URL)
        await conn.execute("ALTER TABLE interaction_logs ADD COLUMN IF NOT EXISTS token_usage INTEGER DEFAULT 0;")
        await conn.close()
        print("✅ Fixed interaction_logs table.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(fix_logs())

