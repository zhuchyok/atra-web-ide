import asyncio
import asyncpg
from datetime import datetime, timedelta

async def check_stats():
    try:
        # Пытаемся подключиться к БД
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
        eight_hours_ago = now - timedelta(hours=8)
        
        # Общая статистика
        total = await conn.fetchval('SELECT count(*) FROM tasks')
        pending = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'pending\'')
        in_progress = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'in_progress\'')
        completed_total = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'completed\'')
        failed = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'failed\'')
        
        # Статистика за последние 8 часов
        new_8h = await conn.fetchval('SELECT count(*) FROM tasks WHERE created_at > $1', eight_hours_ago)
        completed_8h = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'completed\' AND updated_at > $1', eight_hours_ago)
        failed_8h = await conn.fetchval('SELECT count(*) FROM tasks WHERE status = \'failed\' AND updated_at > $1', eight_hours_ago)
        
        print(f"--- ОБЩАЯ СТАТИСТИКА ---")
        print(f"Всего задач в БД: {total}")
        print(f"Ожидают (pending): {pending}")
        print(f"В работе (in_progress): {in_progress}")
        print(f"Завершено (completed): {completed_total}")
        print(f"Провалено (failed): {failed}")
        
        print(f"\n--- ЗА ПОСЛЕДНИЕ 8 ЧАСОВ ---")
        print(f"Новых задач создано: {new_8h}")
        print(f"Завершено успешно: {completed_8h}")
        print(f"Провалено: {failed_8h}")
        
        # Если есть активные задачи, выведем топ-5 последних
        if in_progress > 0:
            print(f"\n--- ТЕКУЩИЕ ЗАДАЧИ (IN_PROGRESS) ---")
            active_tasks = await conn.fetch('SELECT id, title, created_at FROM tasks WHERE status = \'in_progress\' ORDER BY created_at DESC LIMIT 5')
            for task in active_tasks:
                print(f"ID: {task['id']} | {task['title']} | Создана: {task['created_at']}")

        await conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_stats())
