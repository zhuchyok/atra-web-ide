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

async def clear_and_push_one():
    client = await redis_manager.get_client()
    # 1. Clear stream
    await client.delete('stream:expert_tasks')
    print("✅ Redis stream expert_tasks cleared")

    # 2. Reset group
    try:
        await client.xgroup_setid('stream:expert_tasks', 'expert_workers', '0-0')
        print("✅ Group expert_workers reset to 0-0")
    except Exception as e:
        print(f"Error resetting group: {e}")

    # 3. Push ONLY ONE task
    t = {'id': 'a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d', 'expert': 'Игорь', 'name': 'backend_api', 'path': '/app/backend/app/routers'}

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
    await redis_manager.release_task_lock(t['id'])

    payload = json.dumps(task_data)
    await client.xadd('stream:expert_tasks', {'payload': payload})
    print(f"✅ Task {t['id']} for {t['name']} pushed to Redis with phi3.5:3.8b")

if __name__ == '__main__':
    asyncio.run(clear_and_push_one())
