import asyncio
import asyncpg
import json
from datetime import datetime, timedelta

async def scan_db():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:6432/knowledge_os')
        now = datetime.now()
        twelve_hours_ago = now - timedelta(hours=12)
        
        stats_query = """
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                COUNT(*) FILTER (WHERE status = 'pending') as pending
            FROM tasks 
            WHERE created_at > $1 OR updated_at > $1
        """
        stats = await conn.fetchrow(stats_query, twelve_hours_ago)
        
        stuck_query = """
            SELECT id, title, task_type, updated_at 
            FROM tasks 
            WHERE status = 'in_progress' 
            AND updated_at < $1
            LIMIT 10
        """
        stuck_tasks = await conn.fetch(stuck_query, now - timedelta(hours=1))
        
        errors_query = """
            SELECT id, title, result as error, updated_at 
            FROM tasks 
            WHERE status = 'failed' 
            AND updated_at > $1
            ORDER BY updated_at DESC
            LIMIT 5
        """
        recent_errors = await conn.fetch(errors_query, twelve_hours_ago)

        report = {
            'stats_12h': dict(stats) if stats else {},
            'stuck_tasks_count': len(stuck_tasks),
            'stuck_examples': [dict(t) for t in stuck_tasks],
            'recent_errors': [dict(e) for e in recent_errors]
        }
        print(json.dumps(report, indent=2, default=str))
        await conn.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(scan_db())
