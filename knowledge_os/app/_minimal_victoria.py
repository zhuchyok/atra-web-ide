"""Minimal Victoria Router - bypasses complex ai_core"""

import asyncio
import json
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Request(BaseModel):
    goal: str


class Response(BaseModel):
    status: str
    output: str = ""


async def ollama_generate(prompt: str) -> str:
    """Direct Ollama call"""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
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
    output = await ollama_generate(request.goal)
    return {"status": "success", "output": output, "knowledge": {"source": "ollama"}}


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "Victoria-Mini"}
