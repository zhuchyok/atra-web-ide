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

async def clear_all():
    client = await redis_manager.get_client()
    await client.delete('stream:expert_tasks')
    print("✅ Redis stream expert_tasks deleted")
    try:
        await client.xgroup_destroy('stream:expert_tasks', 'expert_workers')
        print("✅ Group expert_workers destroyed")
    except:
        pass

if __name__ == '__main__':
    asyncio.run(clear_all())
