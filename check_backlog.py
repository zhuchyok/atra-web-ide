import asyncio
import asyncpg
from datetime import datetime, timedelta

async def check_backlog():
    try:
        # Пытаемся подключиться к БД (порт 6432 для pgbouncer или 5432 прямой)
        conn = None
        for port in [6432, 5432]:
            try:
                conn = await asyncpg.connect(f'postgresql://admin:secret@localhost:{port}/knowledge_os')
                break
            except:
                continue
        
        if not conn:
            print("ERROR: Could not connect to database")
            return
        
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        three_days_ago = now - timedelta(days=3)
        
        # 1. Зависшие задачи (созданы > 24ч назад и не завершены)
        stuck_tasks = await conn.fetch('''
            SELECT id, title, status, created_at 
            FROM tasks 
            WHERE status IN ('pending', 'in_progress') 
            AND created_at < $1 
            ORDER BY created_at ASC
        ''', day_ago)
        
        # 2. Среднее время выполнения (за последние 3 дня)
        avg_time = await conn.fetchval('''
            SELECT AVG(updated_at - created_at) 
            FROM tasks 
            WHERE status = 'completed' 
            AND updated_at > $1
        ''', three_days_ago)
        
        # 3. Очередь (pending)
        pending_count = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'pending'")
        
        print(f"--- АНАЛИЗ УСПЕВАЕМОСТИ ---")
        print(f"Задач в очереди (pending): {pending_count}")
        print(f"Среднее время выполнения (за 3 дня): {avg_time}")
        print(f"Зависших задач (>24ч): {len(stuck_tasks)}")
        
        if stuck_tasks:
            print(f"\n--- ТОП-5 ЗАВИСШИХ ЗАДАЧ ---")
            for t in stuck_tasks[:5]:
                created_str = t['created_at'].strftime('%Y-%m-%d %H:%M')
                print(f"[{t['status'].upper()}] {created_str} | {t['title'][:60]}...")

        await conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_backlog())
