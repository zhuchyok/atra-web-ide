import asyncio
import asyncpg
import json
from datetime import datetime, timedelta

async def analyze_stuck_tasks():
    try:
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
        
        # 1. Получаем детальную информацию о зависших задачах
        stuck_tasks = await conn.fetch('''
            SELECT id, title, status, created_at, updated_at, project_context, goal, result, metadata
            FROM tasks 
            WHERE status IN ('pending', 'in_progress') 
            AND created_at < $1 
            ORDER BY created_at ASC
        ''', day_ago)
        
        print(f"--- АНАЛИЗ ЗАВИСШИХ ЗАДАЧ ({len(stuck_tasks)}) ---")
        
        for t in stuck_tasks:
            print(f"\nID: {t['id']}")
            print(f"TITLE: {t['title']}")
            print(f"STATUS: {t['status']}")
            print(f"CREATED: {t['created_at']}")
            print(f"LAST UPDATE: {t['updated_at']}")
            
            # Проверяем метаданные на наличие ошибок
            if t['metadata']:
                try:
                    meta = json.loads(t['metadata']) if isinstance(t['metadata'], str) else t['metadata']
                    if 'error' in meta:
                        print(f"ERROR IN METADATA: {meta['error']}")
                    if 'last_error' in meta:
                        print(f"LAST ERROR IN METADATA: {meta['last_error']}")
                except:
                    pass
            
            if t['result']:
                print(f"PARTIAL RESULT: {str(t['result'])[:200]}...")
            
            # Попробуем найти последние логи для этой задачи в knowledge_nodes
            # Используем поиск по подстроке в content (text)
            logs = await conn.fetch('''
                SELECT content, created_at 
                FROM knowledge_nodes 
                WHERE (content LIKE $1 OR content LIKE $2)
                AND type IN ('log', 'evolution_log', 'task_result')
                ORDER BY created_at DESC LIMIT 3
            ''', f'%{t["id"]}%', f'%"task_id": "{t["id"]}"%')
            
            if logs:
                print("RECENT LOGS FROM KNOWLEDGE_NODES:")
                for log in logs:
                    print(f"  [{log['created_at']}] {str(log['content'])[:150]}...")
            else:
                print("No specific logs found in knowledge_nodes.")

        # 2. Проверяем состояние воркеров
        recent_updates = await conn.fetchval('''
            SELECT count(*) FROM tasks WHERE updated_at > NOW() - INTERVAL '10 minutes'
        ''')
        print(f"\nАктивность за последние 10 минут (обновлений задач): {recent_updates}")
        
        if recent_updates == 0:
            print("⚠️ ВНИМАНИЕ: За последние 10 минут не было обновлений задач. Возможно, воркеры упали или простаивают.")

        await conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(analyze_stuck_tasks())
