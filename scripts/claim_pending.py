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

async def check_and_claim():
    client = await redis_manager.get_client()
    stream = 'stream:expert_tasks'
    group = 'expert_workers'
    
    try:
        pending = await client.xpending(stream, group)
        print(f"Pending summary: {pending}")
        
        count = pending.get('pending', 0)
        if count > 0:
            # Get detailed pending info
            details = await client.xpending_range(stream, group, '-', '+', 10)
            for d in details:
                print(f"Pending message: {d['message_id']}, consumer: {d['consumer']}, idle: {d['time_since_delivered']}")
                # Claim it
                claimed = await client.xclaim(stream, group, 'debug_consumer', 0, [d['message_id']])
                print(f"Claimed: {len(claimed)} messages")
                for msg in claimed:
                    print(f"Payload: {msg[1]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(check_and_claim())
