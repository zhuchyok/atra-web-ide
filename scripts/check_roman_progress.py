import asyncio
import os
import sys
import asyncpg
import json

async def check_roman_progress():
    db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@knowledge_postgres:5432/knowledge_os')
    conn = await asyncpg.connect(db_url)

    print("--- Roman's Latest Events ---")
    events = await conn.fetch("""
        SELECT event_type, payload, created_at
        FROM actor_events
        WHERE actor_name = 'Роман'
        ORDER BY created_at DESC
        LIMIT 20
    """)
    for e in events:
        payload = e['payload'][:100] + "..." if len(e['payload']) > 100 else e['payload']
        print(f"{e['created_at'].strftime('%H:%M:%S')} | {e['event_type']} | {payload}")

    print("\n--- R&D Tasks Status ---")
    tasks = await conn.fetch("""
        SELECT id, title, status, completed_at, result
        FROM tasks
        WHERE id::text LIKE 'RD_%'
    """)
    for t in tasks:
        res_len = len(t['result']) if t['result'] else 0
        print(f"Task {t['id']}: {t['status']} (completed: {t['completed_at']}, res_len: {res_len})")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_roman_progress())
