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

async def setup_group():
    client = await redis_manager.get_client()
    try:
        await client.xgroup_create('stream:expert_tasks', 'expert_workers', id='0-0', mkstream=True)
        print("✅ Group expert_workers created")
    except Exception as e:
        print(f"Group might already exist or error: {e}")
        try:
            await client.xgroup_setid('stream:expert_tasks', 'expert_workers', '0-0')
            print("✅ Group expert_workers reset to 0-0")
        except Exception as e2:
            print(f"Error resetting group: {e2}")

if __name__ == '__main__':
    asyncio.run(setup_group())
