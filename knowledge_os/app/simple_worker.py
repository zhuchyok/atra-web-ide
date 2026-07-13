"""
Simple Worker - processes code tasks in isolation
"""

import asyncio
import json
import os
import sys


async def process_task(goal: str) -> str:
    """Process goal via direct Ollama call"""
    import aiohttp

    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "http://host.docker.internal:11434/api/generate",
                json={"model": "qwen3.5:35b", "prompt": goal, "stream": False},
                timeout=aiohttp.ClientTimeout(total=120),
            )
            if resp.status == 200:
                data = await resp.json()
                return data.get("response", "")
    except Exception as e:
        return f"Error: {e}"
    return "No response"


async def main():
    """Main loop - read from queue"""
    import time

    import redis

    REDIS_URL = os.getenv("REDIS_URL", "redis://knowledge_os_redis:6379/0")
    r = redis.from_url(REDIS_URL, decode_responses=True)
    print("Worker started, waiting for tasks...")

    while True:
        try:
            # Blocking pop from queue
            result = r.blpop("victoria_queue", timeout=5)
            if result:
                _, data = result
                task = json.loads(data)
                goal = task.get("goal", "")
                task_id = task.get("task_id", "unknown")

                print(f"Processing: {task_id}")
                output = await process_task(goal)

                # Save result
                r.set(f"result:{task_id}", json.dumps({"status": "success", "output": output}))
                print(f"Completed: {task_id}")
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
