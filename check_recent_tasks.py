import asyncpg
import asyncio
import json

async def check():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:5432/knowledge_os')
        tasks = await conn.fetch('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10')
        print(json.dumps([dict(t) for t in tasks], indent=2, default=str, ensure_ascii=False))
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
