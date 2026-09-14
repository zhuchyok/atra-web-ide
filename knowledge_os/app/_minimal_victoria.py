"""Minimal Victoria Router - bypasses complex recursion"""

import asyncio
import json
import os

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class Request(BaseModel):
    goal: str


async def ollama_generate(prompt: str) -> str:
    """Direct Ollama call"""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "http://host.docker.internal:11434/api/generate",
                json={"model": "qwen3.5:35b", "prompt": prompt, "stream": False},
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
    except Exception as e:
        return f"Error: {e}"
    return "No response"


@app.post("/run")
async def run(request: Request):
    # Simple test - just return
    if len(request.goal) < 50:
        return {"status": "success", "output": f"Echo: {request.goal}"}

    # Code generation -> Celery
    if any(kw in request.goal.lower() for kw in ["code", "код", "писать", "создай"]):
        try:
            import redis

            r = redis.from_url(REDIS_URL)
            task_id = f"task_{os.urandom(4).hex()}"
            r.rpush("victoria_queue", json.dumps({"goal": request.goal, "task_id": task_id}))
            return {"status": "queued", "job_id": task_id, "output": f"⏳ Task {task_id} queued"}
        except Exception as e:
            pass

    output = await ollama_generate(request.goal)
    return {"status": "success", "output": output, "knowledge": {"source": "ollama"}}


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Victoria-Mini"}
