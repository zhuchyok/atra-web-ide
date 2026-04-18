import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

import aiohttp
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/filesearch", tags=["filesearch"])


class FileSearchRequest(BaseModel):
    query: str
    max_results: int = 10
    filters: Optional[dict] = None


class FileSearchResult(BaseModel):
    id: str
    filename: str
    snippet: str
    score: float
    metadata: dict


class FileSearchResponse(BaseModel):
    results: list[FileSearchResult]
    query: str
    total: int


_file_store: dict[str, dict] = {}
_index: list[dict] = []


async def index_file_content(filename: str, content: str) -> str:
    file_id = f"file_{uuid.uuid4().hex[:12]}"

    chunks = _split_into_chunks(content, chunk_size=1000, overlap=100)

    for i, chunk in enumerate(chunks):
        chunk_id = f"{file_id}_chunk_{i}"
        _index.append(
            {
                "id": chunk_id,
                "file_id": file_id,
                "filename": filename,
                "content": chunk,
                "indexed_at": int(datetime.now().timestamp()),
            }
        )

    _file_store[file_id] = {
        "id": file_id,
        "filename": filename,
        "size": len(content),
        "chunks": len(chunks),
        "indexed_at": int(datetime.now().timestamp()),
    }

    return file_id


def _split_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if overlap > 0 and start > 0:
            chunk = text[start - overlap : start] + chunk

        chunks.append(chunk.strip())
        start += chunk_size - overlap

    return chunks


def _calculate_relevance(chunk: str, query: str, filters: dict = None) -> float:
    query_terms = set(query.lower().split())
    chunk_lower = chunk.lower()

    term_matches = sum(1 for term in query_terms if term in chunk_lower)
    relevance = term_matches / len(query_terms) if query_terms else 0

    if filters:
        for key, value in filters.items():
            if key.lower() in chunk_lower and str(value).lower() in chunk_lower:
                relevance += 0.5

    return min(relevance, 1.0)


@router.post("/search", response_model=FileSearchResponse)
async def search_files(request: FileSearchRequest):
    query = request.query.lower()
    max_results = request.max_results
    filters = request.filters or {}

    scored_results = []

    for chunk in _index:
        if filters and filters.get("file_id") and chunk.get("file_id") != filters["file_id"]:
            continue

        relevance = _calculate_relevance(chunk["content"], query, filters)

        if relevance > 0:
            scored_results.append(
                {
                    "id": chunk["id"],
                    "filename": chunk["filename"],
                    "snippet": chunk["content"][:500],
                    "score": relevance,
                    "metadata": {"file_id": chunk["file_id"], "indexed_at": chunk["indexed_at"]},
                }
            )

    scored_results.sort(key=lambda x: x["score"], reverse=True)
    results = scored_results[:max_results]

    return FileSearchResponse(
        results=[FileSearchResult(**r) for r in results], query=request.query, total=len(results)
    )


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")

    file_id = await index_file_content(file.filename, text)

    return {"id": file_id, "filename": file.filename, "size": len(content), "status": "indexed"}


@router.post("/upload/text")
async def upload_text(filename: str = Form(...), content: str = Form(...)):
    file_id = await index_file_content(filename, content)

    return {"id": file_id, "filename": filename, "size": len(content), "status": "indexed"}


@router.get("/files")
async def list_files(limit: int = 50):
    files = sorted(_file_store.values(), key=lambda x: x["indexed_at"], reverse=True)
    return files[:limit]


@router.get("/files/{file_id}")
async def get_file(file_id: str):
    if file_id not in _file_store:
        raise HTTPException(status_code=404, detail="File not found")

    file_info = _file_store[file_id]
    chunks = [c for c in _index if c["file_id"] == file_id]

    return {**file_info, "chunks": chunks}


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    if file_id not in _file_store:
        raise HTTPException(status_code=404, detail="File not found")

    _index[:] = [c for c in _index if c["file_id"] != file_id]
    del _file_store[file_id]

    return {"status": "deleted", "file_id": file_id}


@router.get("/stats")
async def get_stats():
    return {
        "files_count": len(_file_store),
        "chunks_count": len(_index),
        "total_size": sum(f["size"] for f in _file_store.values()),
    }


async def get_file_search_processor() -> dict:
    return {"files": len(_file_store), "indexed_chunks": len(_index)}
