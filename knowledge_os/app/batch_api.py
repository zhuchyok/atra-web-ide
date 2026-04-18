import asyncio
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import aiohttp
from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel

router = APIRouter(prefix="/api/batch", tags=["batch"])

BATCH_BASE_URL = "https://api.openai.com/v1"
BATCH_STORAGE_PATH = Path("/tmp/atra_batches")
BATCH_STORAGE_PATH.mkdir(exist_ok=True)


class BatchRequest(BaseModel):
    custom_id: str
    method: str
    url: str
    body: dict


class BatchJobCreate(BaseModel):
    input_file_path: str
    endpoint: str
    completion_window: str = "24h"
    metadata: Optional[dict] = None


class BatchJobStatus(BaseModel):
    id: str
    object: str = "batch"
    created_at: int
    completed_at: Optional[int] = None
    expires_at: Optional[int] = None
    failed_at: Optional[int] = None
    status: str
    input_file_id: str
    output_file_id: Optional[str] = None
    error_file_id: Optional[str] = None
    request_counts: Optional[dict] = None
    completion_window: str
    metadata: Optional[dict] = None


class BatchJobResponse(BaseModel):
    id: str
    object: str
    created_at: int
    status: str
    input_file_id: str
    output_file_id: Optional[str] = None
    request_counts: dict


_batch_jobs: dict[str, BatchJobStatus] = {}
_output_files: dict[str, list[dict]] = {}


def load_jsonl(file_path: str) -> list[dict]:
    results = []
    path = Path(file_path)
    if not path.exists():
        return []
    with open(path) as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))
    return results


def save_jsonl(data: list[dict], file_path: str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")


async def process_batch_job(batch_id: str, background_tasks: BackgroundTasks) -> None:
    batch = _batch_jobs.get(batch_id)
    if not batch:
        return

    try:
        input_file_path = BATCH_STORAGE_PATH / f"input_{batch_id}.jsonl"
        requests = load_jsonl(str(input_file_path))

        completed = []
        failed = []

        for req in requests:
            try:
                result = await execute_batch_request(req, batch.endpoint)
                completed.append({"custom_id": req.get("custom_id"), "response": result})
            except Exception as e:
                failed.append({"custom_id": req.get("custom_id"), "error": str(e)})

        output_path = BATCH_STORAGE_PATH / f"output_{batch_id}.jsonl"
        save_jsonl(completed, str(output_path))

        if failed:
            error_path = BATCH_STORAGE_PATH / f"error_{batch_id}.jsonl"
            save_jsonl(failed, str(error_path))

        batch.status = "completed"
        batch.completed_at = int(datetime.now().timestamp())
        batch.output_file_id = f"file_{batch_id}_output"
        _output_files[batch.output_file_id] = completed

    except Exception as e:
        batch.status = "failed"
        batch.failed_at = int(datetime.now().timestamp())


async def execute_batch_request(req: dict, endpoint: str) -> dict:
    method = req.get("method", "POST")
    url = req.get("url", endpoint)
    body = req.get("body", {})

    custom_id = req.get("custom_id", str(uuid.uuid4()))

    timeout = aiohttp.ClientTimeout(total=300)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            if method == "POST":
                async with session.post(url, json=body) as resp:
                    result = await resp.json()
            elif method == "GET":
                async with session.get(url, params=body) as resp:
                    result = await resp.json()
            else:
                raise ValueError(f"Unsupported method: {method}")

            return {"custom_id": custom_id, "response": result, "status_code": 200}
        except aiohttp.ClientError as e:
            return {"custom_id": custom_id, "error": str(e), "status_code": 500}


@router.post("/jobs", response_model=BatchJobResponse)
async def create_batch_job(
    file: UploadFile = File(...),
    endpoint: str = "/v1/chat/completions",
    completion_window: str = "24h",
    metadata: Optional[dict] = None,
):
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"

    content = await file.read()
    input_path = BATCH_STORAGE_PATH / f"input_{batch_id}.jsonl"
    input_path.write_bytes(content)

    requests = load_jsonl(str(input_path))
    request_count = len(requests)

    batch = BatchJobStatus(
        id=batch_id,
        created_at=int(datetime.now().timestamp()),
        completed_at=None,
        expires_at=int((datetime.now() + timedelta(days=1)).timestamp()),
        status="processing",
        input_file_id=f"file_{batch_id}_input",
        output_file_id=None,
        error_file_id=None,
        request_counts={"total": request_count, "completed": 0, "failed": 0},
        completion_window=completion_window,
        metadata=metadata or {},
    )

    _batch_jobs[batch_id] = batch

    asyncio.create_task(process_batch_job(batch_id, None))

    return BatchJobResponse(
        id=batch.id,
        object=batch.object,
        created_at=batch.created_at,
        status=batch.status,
        input_file_id=batch.input_file_id,
        output_file_id=batch.output_file_id,
        request_counts=batch.request_counts,
    )


@router.get("/jobs/{batch_id}", response_model=BatchJobStatus)
async def get_batch_job(batch_id: str):
    if batch_id not in _batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return _batch_jobs[batch_id]


@router.get("/jobs")
async def list_batch_jobs(limit: int = 100):
    jobs = sorted(_batch_jobs.values(), key=lambda x: x.created_at, reverse=True)
    return jobs[:limit]


@router.get("/jobs/{batch_id}/output")
async def get_batch_output(batch_id: str):
    batch = _batch_jobs.get(batch_id)
    if not batch or not batch.output_file_id:
        raise HTTPException(status_code=404, detail="Output not found")

    output_path = BATCH_STORAGE_PATH / f"output_{batch_id}.jsonl"
    if not output_path.exists():
        return {"data": []}

    return {"data": load_jsonl(str(output_path))}


@router.post("/jobs/{batch_id}/cancel")
async def cancel_batch_job(batch_id: str):
    if batch_id not in _batch_jobs:
        raise HTTPException(status_code=404, detail="Batch job not found")

    batch = _batch_jobs[batch_id]
    if batch.status not in ["validating", "pending", "processing"]:
        raise HTTPException(status_code=400, detail="Cannot cancel batch in current status")

    batch.status = "cancelled"
    return {"id": batch_id, "status": "cancelled"}


@router.post("/input/upload")
async def upload_input_file(file: UploadFile = File(...)):
    file_id = f"file_{uuid.uuid4().hex[:12]}"
    file_path = BATCH_STORAGE_PATH / f"{file_id}.jsonl"

    content = await file.read()
    file_path.write_bytes(content)

    return {
        "id": file_id,
        "object": "file",
        "bytes": len(content),
        "created_at": int(datetime.now().timestamp()),
    }


@router.get("/input/{file_id}")
async def get_input_file(file_id: str):
    file_path = BATCH_STORAGE_PATH / f"{file_id}.jsonl"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return {"path": str(file_path), "size": file_path.stat().st_size}


def create_batch_request(
    custom_id: str, messages: list[dict], model: str = "llama-3.1-8b", **kwargs
) -> dict:
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {"model": model, "messages": messages, **kwargs},
    }


async def get_batch_processor(max_concurrent: int = 5, timeout: float = 300.0) -> dict:
    return {"max_concurrent": max_concurrent, "timeout": timeout, "jobs": _batch_jobs}
