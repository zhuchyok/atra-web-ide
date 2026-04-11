import asyncio
import asyncpg
from datetime import datetime, timedelta
import json

async def analyze_failures():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:6432/knowledge_os')
        hour_ago = datetime.now() - timedelta(hours=1)
        
        print('--- DETAILED FAILED TASKS (LAST 1H) ---')
        failures = await conn.fetch("""
            SELECT id, title, result, updated_at, metadata
            FROM tasks 
            WHERE status = 'failed' 
            AND updated_at > $1
            ORDER BY updated_at DESC
        """, hour_ago)
        
        if not failures:
            print("No failures found in the last hour.")
            return

        for f in failures:
            print(f"ID: {f['id']}")
            print(f"Title: {f['title']}")
            res = f['result'] or "No result"
            print(f"Error: {res[:300]}...")
            meta = f['metadata'] or {}
            print(f"Metadata: {meta}")
            print("-" * 40)
            
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(analyze_failures())
