import asyncio
import asyncpg
from datetime import datetime, timedelta

async def check_failed_details():
    try:
        conn = await asyncpg.connect('postgresql://admin:secret@localhost:6432/knowledge_os')
        
        print("--- FAILED TASKS ANALYSIS ---")
        
        # Группировка по ошибкам (если есть поле error или в описании)
        # В нашей схеме обычно ошибки пишутся в description или logs, проверим структуру
        # Сначала просто топ 10 проваленных задач
        failed_tasks = await conn.fetch("SELECT id, title, description, updated_at FROM tasks WHERE status = 'failed' ORDER BY updated_at DESC LIMIT 10")
        
        for t in failed_tasks:
            print(f"ID: {t['id']}")
            print(f"Title: {t['title']}")
            print(f"Updated: {t['updated_at']}")
            # Выводим кусочек описания, там часто причина
            desc = (t['description'] or "")[:200]
            print(f"Desc: {desc}...")
            print("-" * 30)
            
        # Проверим, сколько задач было удалено (если есть логи очистки или по разнице)
        # Но мы можем просто посмотреть, есть ли задачи старше 3 дней в статусе failed
        three_days_ago = datetime.now() - timedelta(days=3)
        old_failed = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'failed' AND updated_at < $1", three_days_ago)
        print(f"\nFailed tasks older than 3 days: {old_failed}")
        
        await conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check_failed_details())
