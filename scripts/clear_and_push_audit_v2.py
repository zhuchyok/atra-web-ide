import asyncio
import os
import sys
import json

# Add paths for imports
sys.path.insert(0, '/app/knowledge_os/app')
sys.path.insert(0, '/app')

try:
    from redis_manager import redis_manager
except ImportError:
    sys.path.insert(0, os.path.join(os.getcwd(), 'knowledge_os', 'app'))
    from redis_manager import redis_manager

async def clear_and_push():
    client = await redis_manager.get_client()
    # 1. Clear stream
    await client.delete('stream:expert_tasks')
    print("✅ Redis stream expert_tasks cleared")

    # 2. Recreate group
    try:
        await client.xgroup_create('stream:expert_tasks', 'expert_workers', mkstream=True)
        print("✅ Group expert_workers created")
    except Exception as e:
        print(f"Group might already exist or error: {e}")
        try:
            await client.xgroup_setid('stream:expert_tasks', 'expert_workers', '0-0')
            print("✅ Group expert_workers reset to 0-0")
        except Exception as e2:
            print(f"Error resetting group: {e2}")

    # 3. Push tasks
    tasks = [
        {'id': '76ba91b0-6a1f-4290-8ddd-cf76f46a5f8e', 'expert': 'Игорь', 'name': 'backend_api', 'path': '/app/backend/app/routers'},
        {'id': '905748c5-8187-420a-b6ab-16eeb667dec7', 'expert': 'Игорь', 'name': 'backend_services', 'path': '/app/backend/app/services'},
        {'id': 'd1fd6417-ff32-4bf9-bb74-3f0950b74010', 'expert': 'Виктория', 'name': 'knowledge_os', 'path': '/app/knowledge_os'},
        {'id': '789e37d9-5f54-49a1-b669-6246aad0bdbe', 'expert': 'Виктория', 'name': 'agents', 'path': '/app/src/agents'},
        {'id': '707379ef-22aa-44c0-90c1-a94ebd59be21', 'expert': 'Ольга', 'name': 'rust_core', 'path': '/app/rust_core'}
    ]

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
                'model_hint': 'deepseek-r1:14b',
                'module': t['name'],
                'path': t['path']
            }
        }
        # Release lock just in case
        await redis_manager.release_task_lock(t['id'])

        # Push to stream
        payload = json.dumps(task_data)
        await client.xadd('stream:expert_tasks', {'payload': payload})
        print(f"✅ Task {t['id']} for {t['name']} pushed to Redis with deepseek-r1:14b")

if __name__ == '__main__':
    asyncio.run(clear_and_push())
