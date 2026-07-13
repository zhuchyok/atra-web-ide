#!/usr/bin/env python3
"""Simple worker for Victoria"""

import asyncio
import json

import aiohttp
import redis


async def worker():
    r = redis.Redis(host="redis", port=6379, decode_responses=True)
    print("Worker connected to Redis")

    while True:
        try:
            result = r.blpop("victoria_queue", timeout=2)
            if result:
                _, data = result
                task = json.loads(data)
                task_id = task.get("task_id", "unknown")
                goal = task.get("goal", "")

                print(f"Processing {task_id}")

                # Call Ollama
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        "http://host.docker.internal:11434/api/generate",
                        json={"model": "qwen3.5:35b", "prompt": goal, "stream": False},
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            output = d.get("response", "")[:5000]
                            r.set(
                                f"result:{task_id}",
                                json.dumps({"status": "success", "output": output}),
                            )
                            print(f"Done {task_id}")
        except Exception as e:
            print(f"Error: {e}")
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(worker())
