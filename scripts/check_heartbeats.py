import asyncio
import sys
sys.path.append('/app/knowledge_os/app')
from redis_manager import redis_manager

async def check_heartbeats():
    client = await redis_manager.get_client()
    keys = await client.keys("blackboard:heartbeat:*")
    print(f"Active Heartbeats: {len(keys)}")
    for key in keys:
        owner = await client.get(key)
        ttl = await client.ttl(key)
        print(f" - {key}: owner={owner}, ttl={ttl}s")

if __name__ == "__main__":
    asyncio.run(check_heartbeats())
