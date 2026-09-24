import asyncio
import os
import sys
import json
import asyncpg

# Добавляем пути для импорта
sys.path.insert(0, '/app/knowledge_os/app')
sys.path.insert(0, '/app')

try:
    from redis_manager import redis_manager
except ImportError:
    # Fallback for local run
    sys.path.insert(0, os.path.join(os.getcwd(), 'knowledge_os', 'app'))
    from redis_manager import redis_manager

async def get_db_pool():
    db_url = os.getenv("DATABASE_URL")
    return await asyncpg.create_pool(db_url)

async def run():
    # 1. Clear stream
    client = await redis_manager.get_client()
    await client.delete('stream:expert_tasks')
    print("✅ Stream expert_tasks cleared")

    # 2. Push tasks
    tasks = [
        {'id': '76ba91b0-6a1f-4290-8ddd-cf76f46a5f8e', 'expert': 'Игорь', 'name': 'backend_api', 'path': '/app/backend/app/routers'},
        {'id': '905748c5-8187-420a-b6ab-16eeb667dec7', 'expert': 'Игорь', 'name': 'backend_services', 'path': '/app/backend/app/services'},
        {'id': 'd1fd6417-ff32-4bf9-bb74-3f0950b74010', 'expert': 'Виктория', 'name': 'knowledge_os', 'path': '/app/knowledge_os'},
        {'id': '789e37d9-5f54-49a1-b669-6246aad0bdbe', 'expert': 'Виктория', 'name': 'agents', 'path': '/app/src/agents'},
        {'id': '707379ef-22aa-44c0-90c1-a94ebd59be21', 'expert': 'Ольга', 'name': 'rust_core', 'path': '/app/rust_core'}
    ]

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        for t in tasks:
            description = f"Deep audit of {t['path']}. Check architecture, security, error handling. Use read_file and list_directory. [force_ollama] preferred_source: ollama"
            task_data = {
                'task_id': t['id'],
                'expert_name': t['expert'],
                'description': description,
                'category': 'coding',
                'metadata': {
                    'complex': True,
                    'preferred_source': 'ollama',
                    'model_hint': 'phi3.5:3.8b',
                    'module': t['name'],
                    'path': t['path']
                }
            }
            # Force push by clearing lock first
            await redis_manager.release_task_lock(t['id'])

            # Update metadata in DB
            await conn.execute(
                "UPDATE tasks SET metadata = COALESCE(metadata, '{}'::jsonb) || $2::jsonb, status = 'pending' WHERE id = $1",
                t['id'],
                json.dumps(task_data['metadata'])
            )

            await redis_manager.push_to_stream('expert_tasks', task_data)
            print(f"✅ Task {t['id']} for {t['name']} pushed to Redis and DB updated")

if __name__ == '__main__':
    asyncio.run(run())
