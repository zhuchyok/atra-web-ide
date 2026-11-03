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
_fallback_raw = os.getenv("EMBED_FALLBACK_URLS", "")
_fallback_urls = [u.strip().rstrip("/") for u in _fallback_raw.split(",") if u.strip()]
_embed_endpoints = [OLLAMA_URL.rstrip("/"), *_fallback_urls]
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
    errors: list[str] = []
    saw_overload = False
    for endpoint in _embed_endpoints:
        async with _semaphore:
            response = await _client.post(
                f"{endpoint}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
        if response.status_code == 200:
            embedding = response.json().get("embedding")
            if embedding and len(embedding) == EMBEDDING_DIM:
                return embedding
            errors.append(
                f"{endpoint}: bad_dim={len(embedding) if embedding else 0} expected={EMBEDDING_DIM}"
            )
            continue
        if response.status_code in (429, 500, 503):
            saw_overload = True
            _upstream_cooldown_until_ts = max(
                _upstream_cooldown_until_ts,
                asyncio.get_event_loop().time() + _UPSTREAM_COOLDOWN_SEC,
            )
            errors.append(f"{endpoint}: overloaded({response.status_code})")
            continue
        if response.status_code in (400, 404):
            errors.append(f"{endpoint}: model_unavailable({response.status_code})")
            continue
        errors.append(f"{endpoint}: http_{response.status_code}")

    if saw_overload:
        raise HTTPException(status_code=503, detail="all embedding upstreams overloaded")
    raise HTTPException(status_code=500, detail="; ".join(errors) or "embedding upstream failed")


@app.get("/health")
async def health():
    issues: list[str] = []
    available_on: list[str] = []
    try:
        for endpoint in _embed_endpoints:
            try:
                r = await _client.get(f"{endpoint}/api/tags", timeout=5.0)
                models = [m.get("name", "") for m in r.json().get("models", [])]
                if any(m.startswith(EMBED_MODEL) for m in models):
                    available_on.append(endpoint)
            except Exception as exc:
                issues.append(f"{endpoint}:{exc}")
        model_ok = bool(available_on)
        return {
            "status": "healthy" if model_ok else "degraded",
            "backend": "ollama",
            "model": EMBED_MODEL,
            "model_available": model_ok,
            "available_on": available_on,
            "issues": issues,
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
