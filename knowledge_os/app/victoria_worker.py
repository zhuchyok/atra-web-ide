#!/usr/bin/env python3
"""Victoria Worker - processes code tasks from PostgreSQL queue (not Redis)"""

import asyncio
import redis
import json
import aiohttp
import os
import sys
import asyncpg


POSTGRES_URL = os.getenv("POSTGRES_DIRECT_URL", "postgresql://admin:secret@knowledge_postgres:5432/knowledge_os")
REDIS_URL = os.getenv("REDIS_URL", "redis://knowledge_os_redis:6379/0")

r = redis.from_url(REDIS_URL, decode_responses=False)


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
            async with session.post(
                f"{victoria_url}/run?async_mode=true",
                json={"goal": goal},
                timeout=aiohttp.ClientTimeout(total=300),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    output = data.get("output", "")[:5000]
                    r.set(
                        f"task:{task_id}",
                        json.dumps({
                            "task_id": task_id,
                            "status": "completed",
                            "output": output,
                            "knowledge": {"strategy": "worker"},
                        }),
                    )
                    print(f"Done {task_id}", flush=True)
                    return
    except Exception as e:
        print(f"Victoria call failed: {e}", flush=True)

    # Fallback to direct Ollama
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://host.docker.internal:11434/api/generate",
                json={"model": "qwen3.5:35b", "prompt": goal, "stream": False},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    output = data.get("response", "")[:5000]
                    r.set(
                        f"task:{task_id}",
                        json.dumps({
                            "task_id": task_id,
                            "status": "completed",
                            "output": output,
                            "knowledge": {"strategy": "worker_fallback"},
                        }),
                    )
                    print(f"Done {task_id} (fallback)", flush=True)
                    return
    except Exception as e:
        print(f"Fallback error: {e}", flush=True)

    r.set(
        f"task:{task_id}",
        json.dumps({"task_id": task_id, "status": "failed", "output": str(e), "knowledge": {}}),
    )


async def worker_loop():
    """Main loop - read from PostgreSQL tasks table"""
    print("Worker starting...", flush=True)
    
    # Connect to PostgreSQL
    pool = await asyncpg.create_pool(POSTGRES_URL, min_size=2, max_size=5)
    print("Connected to PostgreSQL", flush=True)

    await wait_for_victoria()
    print("Victoria ready, starting processing...", flush=True)

    while True:
        try:
            async with pool.acquire() as conn:
                # Atomically claim a pending task from tasks table
                # Looking for tasks with metadata->>'source' = 'victoria_queue'
                result = await conn.execute("""
                    UPDATE tasks
                    SET status = 'in_progress', updated_at = NOW()
                    WHERE id IN (
                        SELECT id FROM tasks 
                        WHERE status = 'pending' 
                        AND metadata->>'source' = 'victoria_queue'
                        ORDER BY created_at ASC
                        LIMIT 1
                    )
                    RETURNING id, title, description, metadata
                """)
                
                # Check if we got a task (result contains UPDATE with row count)
                if "UPDATE 1" in result:
                    # Fetch the claimed task
                    task = await conn.fetchrow("""
                        SELECT id, title, description, metadata 
                        FROM tasks 
                        WHERE metadata->>'source' = 'victoria_queue' 
                        AND status = 'in_progress'
                        ORDER BY created_at ASC 
                        LIMIT 1
                    """)
                    
                    if task:
                        task_id = str(task['id'])
                        goal = task['description'] or task['title'] or ''
                        
                        print(f"Processing task {task_id}: {goal[:50]}...", flush=True)
                        
                        # Process the task
                        await process_task(goal, task_id)
                        
                        # Mark as completed
                        await conn.execute("""
                            UPDATE tasks 
                            SET status = 'completed', updated_at = NOW(), completed_at = NOW()
                            WHERE id = $1
                        """, task_id)
                        
                        print(f"Completed task {task_id}", flush=True)
                        
        except Exception as e:
            print(f"Error: {e}", flush=True)
            await asyncio.sleep(2)

        await asyncio.sleep(1)


if __name__ == "__main__":
    print("Victoria Worker (PostgreSQL mode) starting...", flush=True)
    asyncio.run(worker_loop())
