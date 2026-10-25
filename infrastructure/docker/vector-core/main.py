"""ATRA VectorCore (Ollama backend) — embedding-сервис для дашборда и Knowledge OS.

Совместим по контракту с классическим vector_core.py (SentenceTransformer):
  POST /encode        {"text": "...}            -> {"embedding": [768 floats]}
  POST /encode_batch  {"texts": [...]}          -> {"embeddings": [[...], ...]}
  GET  /health                                  -> {"status": "healthy", ...}
Эмбеддинги считает Ollama (nomic-embed-text, 768 измерений — совпадает с
knowledge_nodes.embedding vector(768)).

[v150.2] Аудит 2026-10-08 (находка №4): раньше каждый async-эндпоинт создавал
СИНХРОННЫЙ httpx.Client и блокировал event loop на весь запрос к Ollama (до 60с,
батчи — минуты) — healthcheck (3с) валился, /encode отдавал 500-е, контейнер
флапал в unhealthy. Теперь: один AsyncClient на процесс, батч — gather с семафором.
"""

import asyncio
import os
from typing import List

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
BATCH_CONCURRENCY = int(os.getenv("EMBED_BATCH_CONCURRENCY", "4"))
BATCH_LIMIT = int(os.getenv("EMBED_BATCH_LIMIT", "64"))

_client = httpx.AsyncClient(timeout=60.0)
_semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)
_UPSTREAM_COOLDOWN_SEC = float(os.getenv("EMBED_UPSTREAM_COOLDOWN_SEC", "5"))
_upstream_cooldown_until_ts = 0.0

app = FastAPI(title="ATRA VectorCore — Embedding Service (Ollama backend)")


class TextRequest(BaseModel):
    text: str


class BatchRequest(BaseModel):
    texts: List[str]


class VectorResponse(BaseModel):
    embedding: List[float]


class BatchResponse(BaseModel):
    embeddings: List[List[float]]


async def _embed(text: str) -> List[float]:
    global _upstream_cooldown_until_ts
    if asyncio.get_event_loop().time() < _upstream_cooldown_until_ts:
        raise HTTPException(status_code=503, detail="upstream embeddings cooldown active")
    async with _semaphore:
        response = await _client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
        )
    if response.status_code in (429, 500, 503):
        _upstream_cooldown_until_ts = max(
            _upstream_cooldown_until_ts, asyncio.get_event_loop().time() + _UPSTREAM_COOLDOWN_SEC
        )
        raise HTTPException(status_code=503, detail=f"ollama overloaded ({response.status_code})")
    response.raise_for_status()
    embedding = response.json().get("embedding")
    if not embedding or len(embedding) != EMBEDDING_DIM:
        raise ValueError(
            f"Ollama вернул {len(embedding) if embedding else 0} измерений, ожидалось {EMBEDDING_DIM}"
        )
    return embedding


@app.get("/health")
async def health():
    try:
        r = await _client.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        models = [m.get("name", "") for m in r.json().get("models", [])]
        model_ok = any(m.startswith(EMBED_MODEL) for m in models)
        return {
            "status": "healthy" if model_ok else "degraded",
            "backend": "ollama",
            "model": EMBED_MODEL,
            "model_available": model_ok,
            "dim": EMBEDDING_DIM,
        }
    except Exception as e:
        return {"status": "degraded", "backend": "ollama", "error": str(e)}


@app.post("/encode", response_model=VectorResponse)
async def encode(request: TextRequest):
    try:
        return {"embedding": await _embed(request.text)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/encode_batch", response_model=BatchResponse)
async def encode_batch(request: BatchRequest):
    if len(request.texts) > BATCH_LIMIT:
        raise HTTPException(
            status_code=413,
            detail=f"batch too large: {len(request.texts)} > {BATCH_LIMIT} (EMBED_BATCH_LIMIT)",
        )
    try:
        return {"embeddings": list(await asyncio.gather(*(_embed(t) for t in request.texts)))}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
