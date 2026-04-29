import asyncio
import json
import sys
sys.path.append('/app/knowledge_os/app')
from redis_manager import redis_manager

async def check_goals_full():
    client = await redis_manager.get_client()
    goals = await client.hgetall("blackboard:goals")
    print(json.dumps({k: json.loads(v) for k, v in goals.items()}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(check_goals_full())
