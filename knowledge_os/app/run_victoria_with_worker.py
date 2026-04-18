#!/usr/bin/env python3
"""
[SINGULARITY 26.10] Combined Victoria + Worker Startup

Запускает Victoria API и Worker в ОДНОМ контейнере, но в РАЗНЫХ процессах.
Рекурсия решена: worker имеет отдельный Python стек.
"""

import asyncio
import multiprocessing
import os
import sys
import time
import signal
import redis
import json
import aiohttp


def run_victoria():
    """Запускает Victoria API (uvicorn)"""
    print("🚀 Starting Victoria API...")
    os.system("python -m src.agents.bridge.victoria_server")


def run_worker():
    """Запускает Worker процесс"""
    print("🔧 Starting Worker process...")

    async def worker_loop():
        r = redis.Redis(host="redis", port=6379, decode_responses=True)
        print("Worker connected to Redis")

        while True:
            try:
                result = r.blpop("victoria_queue", timeout=3)
                if result:
                    _, data = result
                    task = json.loads(data)
                    goal = task.get("goal", "")
                    task_id = task.get("task_id", "unknown")
                    print(f"📝 Processing: {task_id[:12]}")

                    # Call Ollama directly
                    try:
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
                                    print(f"✅ Done: {task_id[:12]}")
                    except Exception as e:
                        r.set(
                            f"result:{task_id}", json.dumps({"status": "error", "output": str(e)})
                        )
                        print(f"❌ Error: {e}")
            except Exception as e:
                pass
            await asyncio.sleep(0.5)

    asyncio.run(worker_loop())


def main():
    print("=" * 50)
    print("🎯 Victoria + Worker Combined Startup")
    print("=" * 50)

    # Start worker in separate process
    worker_proc = multiprocessing.Process(target=run_worker, daemon=True)
    worker_proc.start()

    # Give worker time to start
    time.sleep(2)

    # Start Victoria
    run_victoria()


if __name__ == "__main__":
    main()
