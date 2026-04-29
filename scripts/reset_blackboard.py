import asyncio
import sys
import os

sys.path.append('/app/knowledge_os/app')
from redis_manager import redis_manager

async def reset_system_state():
    client = await redis_manager.get_client()
    
    # 1. Очищаем Blackboard от зависших задач
    await client.delete("blackboard:goals")
    print("✅ Blackboard goals cleared.")
    
    # 2. Очищаем старые аукционы
    keys = await client.keys("blackboard:bids:*")
    if keys:
        await client.delete(*keys)
        print(f"✅ Cleared {len(keys)} old auctions.")
        
    # 3. Очищаем локи
    locks = await client.keys("blackboard:lock:*")
    if locks:
        await client.delete(*locks)
        print(f"✅ Cleared {len(locks)} old locks.")

    # 4. Очищаем стрим (опционально, но полезно для сброса очереди)
    # await client.delete("stream:expert_tasks")
    # print("✅ Task stream cleared.")

if __name__ == "__main__":
    asyncio.run(reset_system_state())
