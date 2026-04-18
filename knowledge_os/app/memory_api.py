import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemoryEntry(BaseModel):
    key: str
    value: str
    metadata: Optional[dict] = None
    ttl: Optional[int] = None


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10


class MemorySearchResult(BaseModel):
    key: str
    value: str
    score: float
    metadata: dict


_memory_store: dict[str, dict] = {}
_history: list[dict] = []


@router.post("/set")
async def set_memory(entry: MemoryEntry):
    entry_id = str(uuid.uuid4())
    now = int(datetime.now().timestamp())

    _memory_store[entry.key] = {
        "id": entry_id,
        "key": entry.key,
        "value": entry.value,
        "metadata": entry.metadata or {},
        "created_at": now,
        "updated_at": now,
        "ttl": entry.ttl,
    }

    _history.append({"action": "set", "key": entry.key, "timestamp": now})

    return {"id": entry_id, "status": "set"}


@router.get("/get/{key}")
async def get_memory(key: str):
    if key not in _memory_store:
        raise HTTPException(status_code=404, detail="Key not found")

    entry = _memory_store[key]

    if entry.get("ttl") and datetime.now().timestamp() - entry["created_at"] > entry["ttl"]:
        del _memory_store[key]
        raise HTTPException(status_code=404, detail="Key expired")

    return entry


@router.get("/keys")
async def list_keys(prefix: Optional[str] = None, limit: int = 100):
    keys = list(_memory_store.keys())

    if prefix:
        keys = [k for k in keys if k.startswith(prefix)]

    return keys[:limit]


@router.delete("/{key}")
async def delete_memory(key: str):
    if key not in _memory_store:
        raise HTTPException(status_code=404, detail="Key not found")

    del _memory_store[key]

    _history.append({"action": "delete", "key": key, "timestamp": int(datetime.now().timestamp())})

    return {"status": "deleted", "key": key}


@router.post("/search")
async def search_memory(request: MemorySearchRequest):
    query_terms = set(request.query.lower().split())

    results = []

    for key, entry in _memory_store.items():
        combined_text = f"{key} {entry['value']}".lower()
        matches = sum(1 for term in query_terms if term in combined_text)
        score = matches / len(query_terms) if query_terms else 0

        if score > 0:
            results.append(
                MemorySearchResult(
                    key=key,
                    value=entry["value"][:200],
                    score=score,
                    metadata=entry.get("metadata", {}),
                )
            )

    results.sort(key=lambda x: x.score, reverse=True)
    return results[: request.limit]


@router.get("/history")
async def get_history(action: Optional[str] = None, limit: int = 50):
    history = _history

    if action:
        history = [h for h in history if h.get("action") == action]

    return history[-limit:]


@router.post("/clear")
async def clear_memory(pattern: Optional[str] = None):
    global _memory_store, _history

    if pattern:
        to_delete = [k for k in _memory_store.keys() if pattern in k]
        for k in to_delete:
            del _memory_store[k]
    else:
        _memory_store = {}

    _history.append(
        {"action": "clear", "pattern": pattern, "timestamp": int(datetime.now().timestamp())}
    )

    return {"status": "cleared", "pattern": pattern}


@router.post("/increment")
async def increment(key: str, delta: int = 1):
    if key not in _memory_store:
        _memory_store[key] = {
            "id": str(uuid.uuid4()),
            "key": key,
            "value": "0",
            "metadata": {},
            "created_at": int(datetime.now().timestamp()),
            "updated_at": int(datetime.now().timestamp()),
            "ttl": None,
        }

    try:
        current = int(_memory_store[key]["value"])
    except ValueError:
        raise HTTPException(status_code=400, detail="Value is not numeric")

    new_value = current + delta
    _memory_store[key]["value"] = str(new_value)
    _memory_store[key]["updated_at"] = int(datetime.now().timestamp())

    return {"key": key, "value": new_value}


@router.post("/append")
async def append(key: str, value: str, separator: str = "\n"):
    if key not in _memory_store:
        _memory_store[key] = {
            "id": str(uuid.uuid4()),
            "key": key,
            "value": "",
            "metadata": {},
            "created_at": int(datetime.now().timestamp()),
            "updated_at": int(datetime.now().timestamp()),
            "ttl": None,
        }

    current = _memory_store[key]["value"]
    new_value = current + separator + value if current else value

    _memory_store[key]["value"] = new_value
    _memory_store[key]["updated_at"] = int(datetime.now().timestamp())

    return {"key": key, "value": new_value}


@router.get("/stats")
async def get_stats():
    return {"entries": len(_memory_store), "history_size": len(_history)}


async def get_memory_processor() -> dict:
    return {"entries": len(_memory_store), "history": len(_history)}
