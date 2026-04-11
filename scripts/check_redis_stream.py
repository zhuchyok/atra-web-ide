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

async def check():
    client = await redis_manager.get_client()
    try:
        info = await client.xinfo_stream('stream:expert_tasks')
        print(f"Stream info: {info}")
    except Exception as e:
        print(f"Error getting stream info: {e}")

    try:
        groups = await client.xinfo_groups('stream:expert_tasks')
        print(f"Groups: {groups}")
    except Exception as e:
        print(f"Error getting groups: {e}")

    messages = await client.xrange('stream:expert_tasks', count=100)
    print(f"Messages count: {len(messages)}")
    for msg_id, data in messages:
        payload = data.get(b'payload') or data.get('payload')
        try:
            p = json.loads(payload)
            print(f"ID: {msg_id}, TaskID: {p.get('task_id')}, Expert: {p.get('expert_name')}")
        except:
            print(f"ID: {msg_id}, Raw Payload: {payload[:50]}...")

if __name__ == '__main__':
    asyncio.run(check())
