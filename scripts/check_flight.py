import asyncio
import json
import asyncpg
import os

async def get_stats():
    db_url = os.getenv('DATABASE_URL', 'postgresql://admin:secret@knowledge_pgbouncer:6432/knowledge_os')
    conn = await asyncpg.connect(db_url)
    
    # Задачи за последний час
    completed = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'completed' AND completed_at > NOW() - INTERVAL '1 hour'")
    pending = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'pending'")
    in_progress = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'in_progress'")
    
    # Последние 5 выполненных задач
    recent_tasks = await conn.fetch("""
        SELECT title, EXTRACT(EPOCH FROM (completed_at - created_at)) as duration
        FROM tasks 
        WHERE status = 'completed' 
        ORDER BY completed_at DESC 
        LIMIT 5
    """)
    
    stats = {
        'completed_last_1h': completed,
        'pending_total': pending,
        'in_progress_total': in_progress,
        'recent_completed': [dict(r) for r in recent_tasks]
    }
    
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    await conn.close()

if __name__ == "__main__":
    asyncio.run(get_stats())
