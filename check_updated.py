import asyncio
import asyncpg
import json

async def check_updated_tasks():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:6432/knowledge_os')
        latest = await conn.fetch("""
            SELECT id, title, status, created_at, updated_at 
            FROM tasks 
            ORDER BY updated_at DESC 
            LIMIT 10
        """)
        
        print(json.dumps([dict(t) for t in latest], indent=2, default=str, ensure_ascii=False))
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_updated_tasks())
