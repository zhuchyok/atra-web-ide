import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import faiss
import httpx
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Victoria Visual Search API")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
INDEX_PATH = "/app/models/visual_index.faiss"
METADATA_PATH = "/app/models/visual_metadata.json"

# nomic-embed-text produces 768-dim vectors; fallback dim for other models
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))

index = None
metadata: List[Dict] = []


class IndexRequest(BaseModel):
    file_path: str
    text_content: Optional[str] = None  # For text/markdown files


class SearchRequest(BaseModel):
    queries: List[str]
    top_k: int = 3


async def get_embedding(text: str) -> np.ndarray:
    """Get real embedding from Ollama nomic-embed-text with retry on 503."""
    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/embed",
                    json={"model": EMBEDDING_MODEL, "input": text},
                )
                if response.status_code == 503:
                    wait = 2**attempt + 1
                    logger.warning("Ollama busy (503), retry %d/5 in %ds", attempt + 1, wait)
                    await asyncio.sleep(wait)
                    continue
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Ollama embed failed: {response.status_code} {response.text[:200]}"
                    )

                data = response.json()
                embeddings = data.get("embeddings") or data.get("embedding")
                if not embeddings:
                    raise RuntimeError(f"No embeddings in response: {data}")

                vec = embeddings[0] if isinstance(embeddings[0], list) else embeddings
                arr = np.array(vec, dtype="float32").reshape(1, -1)

                if arr.shape[1] != EMBED_DIM:
                    logger.warning(
                        "Embedding dim %d != expected %d, rebuilding index", arr.shape[1], EMBED_DIM
                    )

                return arr
        except httpx.TimeoutException:
            wait = 2**attempt + 1
            logger.warning("Ollama timeout, retry %d/5 in %ds", attempt + 1, wait)
            await asyncio.sleep(wait)

    raise RuntimeError("Ollama embed failed after 5 retries")


def _load_metadata() -> List[Dict]:
    if os.path.exists(METADATA_PATH):
        try:
            with open(METADATA_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_metadata(meta: List[Dict]) -> None:
    os.makedirs(os.path.dirname(METADATA_PATH), exist_ok=True)
    with open(METADATA_PATH, "w") as f:
        json.dump(meta, f)


@app.on_event("startup")
async def load_resources():
    global index, metadata, EMBED_DIM
    logger.info(f"Visual Search: embedding model = {EMBEDDING_MODEL} @ {OLLAMA_BASE_URL}")

    metadata = _load_metadata()

    if os.path.exists(INDEX_PATH):
        index = faiss.read_index(INDEX_PATH)
        logger.info(f"✅ Loaded FAISS index: {index.ntotal} vectors (dim={index.d})")
        EMBED_DIM = index.d
    else:
        # Use default dim — don't probe Ollama at startup (may be busy with workers)
        index = faiss.IndexFlatIP(EMBED_DIM)
        logger.info(f"✅ Created new FAISS index (dim={EMBED_DIM}, model={EMBEDDING_MODEL})")


@app.post("/index")
async def index_file(request: IndexRequest):
    global index, metadata, EMBED_DIM

    # Determine text to embed
    if request.text_content:
        text = request.text_content[:4000]
    elif request.file_path and os.path.exists(request.file_path):
        ext = os.path.splitext(request.file_path)[1].lower()
        if ext in (".md", ".txt"):
            with open(request.file_path, encoding="utf-8", errors="ignore") as f:
                text = f.read()[:4000]
        elif ext in (".png", ".jpg", ".jpeg"):
            # For images: use filename + path as description (no vision model required)
            text = f"Image: {os.path.basename(request.file_path)} from {request.file_path}"
        else:
            text = f"Document: {os.path.basename(request.file_path)}"
    else:
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")

    try:
        embedding = await get_embedding(text)

        # Rebuild index if dimension mismatch (e.g. first run or model change)
        if embedding.shape[1] != EMBED_DIM or index.d != embedding.shape[1]:
            logger.warning("Dim mismatch — rebuilding index")
            EMBED_DIM = embedding.shape[1]
            index = faiss.IndexFlatIP(EMBED_DIM)
            metadata = []

        # Normalise for cosine similarity
        faiss.normalize_L2(embedding)
        index.add(embedding)
        embedding_id = str(index.ntotal - 1)

        metadata.append(
            {
                "id": embedding_id,
                "file_path": request.file_path,
                "description": text[:200],
            }
        )

        faiss.write_index(index, INDEX_PATH)
        _save_metadata(metadata)

        return {"status": "success", "embedding_id": embedding_id}

    except Exception as e:
        logger.error(f"Indexing error for {request.file_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
async def search(request: SearchRequest):
    global index, metadata

    if index is None or index.ntotal == 0:
        return {"results": []}

    try:
        all_results = []
        for query in request.queries:
            query_embedding = await get_embedding(query)
            faiss.normalize_L2(query_embedding)

            k = min(request.top_k, index.ntotal)
            distances, indices = index.search(query_embedding, k)

            for i, idx in enumerate(indices[0]):
                if 0 <= idx < len(metadata):
                    res = metadata[idx].copy()
                    res["similarity"] = float(distances[0][i])
                    all_results.append(res)

        # Deduplicate by file_path, keep highest similarity
        seen = {}
        for r in all_results:
            fp = r["file_path"]
            if fp not in seen or r["similarity"] > seen[fp]["similarity"]:
                seen[fp] = r
        results = sorted(seen.values(), key=lambda x: x["similarity"], reverse=True)[
            : request.top_k
        ]

        return {"results": results}

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "vectors": index.ntotal if index else 0,
        "embedding_model": EMBEDDING_MODEL,
        "dim": EMBED_DIM,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
