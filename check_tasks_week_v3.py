import asyncio
import asyncpg
from datetime import datetime, timedelta

async def check_stats():
    try:
        # Используем данные из .env: postgresql://admin:secret@localhost:6432/knowledge_os
        # Но так как мы запускаем локально, порт может быть 5432 (внутри докера 6432 проброшен)
        # Попробуем оба варианта
        for port in [6432, 5432]:
            try:
                conn = await asyncpg.connect(f'postgresql://admin:secret@localhost:{port}/knowledge_os')
                print(f"Connected to port {port}")
                break
            except:
                continue
        else:
            print("ERROR: Could not connect to database on port 6432 or 5432 with admin:secret")
            return
        
        # Всего задач
        total = await conn.fetchval('SELECT count(*) FROM tasks')
        
        # Задачи за последнюю неделю (созданные)
        week_ago = datetime.now() - timedelta(days=7)
        new_tasks = await conn.fetchval('SELECT count(*) FROM tasks WHERE created_at > $1', week_ago)
        
        # Завершенные за неделю
        completed_week = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'completed\' AND updated_at > $1', week_ago)
        
        # Текущий статус
        pending = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'pending\'')
        in_progress = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'in_progress\'')
        failed = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'failed\'')
        
        print(f'TOTAL_TASKS: {total}')
        print(f'NEW_LAST_7_DAYS: {new_tasks}')
        print(f'COMPLETED_LAST_7_DAYS: {completed_week}')
        print(f'CURRENT_PENDING: {pending}')
        print(f'CURRENT_IN_PROGRESS: {in_progress}')
        print(f'CURRENT_FAILED: {failed}')
        
        await conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_stats())
