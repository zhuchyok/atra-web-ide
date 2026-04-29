import asyncio
import json
import os
import sys

# Add path to modules
sys.path.insert(0, os.path.join(os.getcwd(), "knowledge_os/app"))

from redis_manager import redis_manager

async def check_redis():
    client = await redis_manager.get_client()
    stream_name = "stream:expert_tasks"
    group_name = "expert_worker_group"
    
    try:
        stream_info = await client.xinfo_stream(stream_name)
        groups_info = await client.xinfo_groups(stream_name)
        
        pending_total = 0
        for group in groups_info:
            if group['name'] == group_name:
                pending_total = group['pending']
        
        print(json.dumps({
            "stream_length": stream_info['length'],
            "pending_in_group": pending_total,
            "groups": [g['name'] for g in groups_info]
        }, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_redis())
