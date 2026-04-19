#!/usr/bin/env python3
"""Victoria Worker - processes code tasks from Redis queue"""

import asyncio
import redis
import json
import aiohttp
import os
import sys


async def wait_for_victoria(max_retries=30, delay=2):
    """Wait for Victoria to be ready"""
    victoria_url = "http://localhost:8000"
    for i in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{victoria_url}/health", timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        print(f"Victoria ready after {i + 1} attempts", flush=True)
                        return True
        except Exception:
            pass
        await asyncio.sleep(delay)
    return False


async def process_task(goal: str, task_id: str):
    """Process task via Victoria Multi-Agent System (calls with async_mode to skip queue detection)"""
    print(f"Processing {task_id}...", flush=True)

    victoria_url = "http://localhost:8000"

    try:
        async with aiohttp.ClientSession() as session:
            # Use async_mode=true to SKIP queue detection in Victoria (prevents infinite loop)
            async with session.post(
                f"{victoria_url}/run?async_mode=true",
                json={"goal": goal},
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    output = data.get("output", "")[:5000]
                    # Store in Redis with format expected by /run/status endpoint
                    r.set(
                        f"task:{task_id}",
                        json.dumps(
                            {
                                "task_id": task_id,
                                "status": "completed",
                                "output": output,
                                "knowledge": {
                                    "strategy": "victoria_worker",
                                    "source": data.get("knowledge", {}),
                                },
                            }
                        ),
                    )
                    print(f"Done {task_id}", flush=True)
                    return output
    except Exception as e:
        print(f"Error calling Victoria: {e}", flush=True)

    # Fallback: direct Ollama if Victoria fails
    print("Falling back to direct Ollama...", flush=True)
    ollama_url = "http://host.docker.internal:11434"
    model = os.getenv("VICTORIA_MODEL", "victoria-wisdom-v3.5:latest")

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
                    r.set(
                        f"task:{task_id}",
                        json.dumps(
                            {
                                "task_id": task_id,
                                "status": "completed",
                                "output": output,
                                "knowledge": {"strategy": "worker_fallback"},
                            }
                        ),
                    )
                    print(f"Done {task_id} (fallback)", flush=True)
                    return
    except Exception as e:
        print(f"Fallback error: {e}", flush=True)

    # Failed
    r.set(
        f"task:{task_id}",
        json.dumps({"task_id": task_id, "status": "failed", "output": str(e), "knowledge": {}}),
    )


r = redis.Redis(host="redis", port=6379)


async def worker_loop():
    print("Worker connected to Redis", flush=True)

    # Wait for Victoria to be ready before processing
    print("Waiting for Victoria...", flush=True)
    await wait_for_victoria()
    print("Victoria ready, starting processing...", flush=True)

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
