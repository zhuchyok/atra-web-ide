import asyncio
import asyncpg
import os
import json
from datetime import datetime, timedelta

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")

async def check_victoria_activity():
    conn = await asyncpg.connect(DB_URL)

    print("--- Recent Knowledge Nodes (SOPs/Evolution) ---")
    # knowledge_nodes.created_at is timestamp without time zone, so we use LOCALTIMESTAMP
    nodes = await conn.fetch("""
        SELECT id, content, metadata, created_at
        FROM knowledge_nodes
        WHERE created_at > (LOCALTIMESTAMP - INTERVAL '2 hours')
        ORDER BY created_at DESC
        LIMIT 20
    """)
    for n in nodes:
        meta = n['metadata']
        if isinstance(meta, str): meta = json.loads(meta)
        print(f"[{n['created_at']}] ID: {n['id']} | Type: {meta.get('type') if meta else 'None'} | Content: {n['content'][:100]}...")

    print("\n--- Recent Tasks ---")
    tasks = await conn.fetch("""
        SELECT id, title, status, created_at
        FROM tasks
        WHERE created_at > (NOW() - INTERVAL '2 hours')
        ORDER BY created_at DESC
        LIMIT 10
    """)
    for t in tasks:
        print(f"[{t['created_at']}] ID: {t['id']} | Status: {t['status']} | Title: {t['title'][:100]}...")

    print("\n--- Recent Session Context ---")
    sessions = await conn.fetch("""
        SELECT query_text, response_text, created_at
        FROM session_context
        WHERE created_at > (NOW() - INTERVAL '2 hours')
        ORDER BY created_at DESC
        LIMIT 5
    """)
    for s in sessions:
        print(f"[{s['created_at']}] Q: {s['query_text'][:50]} | A: {s['response_text'][:50]}...")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_victoria_activity())
