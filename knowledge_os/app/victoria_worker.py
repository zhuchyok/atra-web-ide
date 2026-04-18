#!/usr/bin/env python3
"""Victoria Worker - processes code tasks from Redis queue"""

import asyncio
import redis
import json
import aiohttp
import os
import sys


async def process_task(goal: str, task_id: str):
    """Process single task via Victoria's model stack (мозг + руки)"""
    print(f"Processing {task_id}...", flush=True)

    ollama_url = "http://host.docker.internal:11434"
    model = os.getenv("VICTORIA_MODEL", "victoria-wisdom-v3.5:latest")
    print(f"Using model: {model}", flush=True)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": goal, "stream": False},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    output = data.get("response", "")[:5000]
                    # Store in Redis with format expected by /run/status endpoint
                    r.set(
                        f"task:{task_id}",
                        json.dumps(
                            {
                                "task_id": task_id,
                                "status": "completed",
                                "output": output,
                                "knowledge": {"strategy": "worker"},
                            }
                        ),
                    )
                    print(f"Done {task_id}", flush=True)
                    return
    except Exception as e:
        print(f"Error: {e}", flush=True)

    # Failed
    r.set(
        f"task:{task_id}",
        json.dumps({"task_id": task_id, "status": "failed", "output": str(e), "knowledge": {}}),
    )


r = redis.Redis(host="redis", port=6379)


async def worker_loop():
    print("Worker connected to Redis", flush=True)

    while True:
        try:
            result = r.blpop("victoria_queue", timeout=5)
            if result:
                _, data = result
                task = json.loads(data)
                task_id = task.get("task_id", "unknown")
                goal = task.get("goal", "")

                await process_task(goal, task_id)

        except Exception as e:
            print(f"Error: {e}", flush=True)

        await asyncio.sleep(1)


if __name__ == "__main__":
    print("Worker starting...", flush=True)
    asyncio.run(worker_loop())
