import asyncio
import os
import sys
import asyncpg
import json

async def check_latest_events():
    db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@knowledge_postgres:5432/knowledge_os')
    conn = await asyncpg.connect(db_url)
    
    # Последние события акторов
    events = await conn.fetch("""
        SELECT actor_name, event_type, payload, created_at 
        FROM actor_events 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    print("--- Latest Actor Events ---")
    for e in events:
        payload_preview = e['payload'][:100] + "..." if len(e['payload']) > 100 else e['payload']
        print(f"{e['created_at'].strftime('%H:%M:%S')} | {e['actor_name']} | {e['event_type']} | {payload_preview}")
    
    # Проверка статуса задач в БД
    tasks = await conn.fetch("""
        SELECT id, title, status, updated_at 
        FROM tasks 
        WHERE status IN ('pending', 'in_progress')
        ORDER BY updated_at DESC
    """)
    
    print("\n--- Active Tasks in DB ---")
    for t in tasks:
        print(f"{t['updated_at'].strftime('%H:%M:%S')} | {t['status']} | {t['title'][:50]}...")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_latest_events())
