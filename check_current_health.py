import asyncio
import asyncpg
import psutil
import os
from datetime import datetime, timedelta

async def check_current_state():
    # 1. Hardware Stats
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    # 2. DB Stats (Recent tasks)
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:6432/knowledge_os')
        
        # Задачи за последний час
        hour_ago = datetime.now() - timedelta(hours=1)
        recent_stats = await conn.fetchrow("""
            SELECT 
                count(*) FILTER (WHERE status = 'completed') as completed,
                count(*) FILTER (WHERE status = 'failed') as failed,
                count(*) FILTER (WHERE status = 'in_progress') as in_progress,
                count(*) FILTER (WHERE status = 'pending') as pending
            FROM tasks 
            WHERE updated_at > $1
        """, hour_ago)
        
        # Общие счетчики
        total_counts = await conn.fetchrow("""
            SELECT 
                count(*) FILTER (WHERE status = 'pending') as pending,
                count(*) FILTER (WHERE status = 'in_progress') as in_progress,
                count(*) FILTER (WHERE status = 'failed') as failed
            FROM tasks
        """)
        
        # Проверка триггеров Health-Aware Backpressure в логах (через DB metadata если есть)
        backpressure_events = await conn.fetchval("""
            SELECT count(*) FROM tasks 
            WHERE metadata->>'source' = 'failed_tasks_analyzer' 
            AND created_at > $1
        """, hour_ago)
        
        await conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
        recent_stats = {'completed': 'N/A', 'failed': 'N/A', 'in_progress': 'N/A', 'pending': 'N/A'}
        total_counts = {'pending': 'N/A', 'in_progress': 'N/A', 'failed': 'N/A'}
        backpressure_events = 'Error'

    print(f"RAM_USED: {mem.percent}%")
    print(f"RAM_AVAILABLE: {mem.available / (1024**3):.2f} GB")
    print(f"SWAP_USED: {swap.used / (1024**3):.2f} GB")
    print(f"--- RECENT (LAST 1H) ---")
    print(f"Completed: {recent_stats['completed']}")
    print(f"Failed: {recent_stats['failed']}")
    print(f"In Progress: {recent_stats['in_progress']}")
    print(f"--- TOTAL ---")
    print(f"Pending: {total_counts['pending']}")
    print(f"In Progress: {total_counts['in_progress']}")
    print(f"Failed: {total_counts['failed']}")
    print(f"--- EVENTS ---")
    print(f"Analyzer/Audit Tasks: {backpressure_events}")

if __name__ == "__main__":
    asyncio.run(check_current_state())
