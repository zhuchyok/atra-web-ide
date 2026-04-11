import asyncio
import asyncpg
from datetime import datetime, timedelta

async def check_titles():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:6432/knowledge_os')
        week_ago = datetime.now() - timedelta(days=7)
        
        print('--- COMPLETED TASKS (LAST 7 DAYS) ---')
        tasks = await conn.fetch("SELECT title FROM tasks WHERE status = 'completed' AND updated_at > $1 ORDER BY updated_at DESC LIMIT 15", week_ago)
        for t in tasks:
            print(f"- {t['title']}")
            
        print('\n--- IN PROGRESS TASKS ---')
        tasks = await conn.fetch("SELECT title FROM tasks WHERE status = 'in_progress' ORDER BY updated_at DESC")
        for t in tasks:
            print(f"- {t['title']}")
            
        print('\n--- PENDING TASKS (LATEST) ---')
        tasks = await conn.fetch("SELECT title FROM tasks WHERE status = 'pending' ORDER BY created_at DESC LIMIT 10")
        for t in tasks:
            print(f"- {t['title']}")
            
        await conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_titles())
