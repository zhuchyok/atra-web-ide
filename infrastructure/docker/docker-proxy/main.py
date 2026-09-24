"""
Docker Proxy — sidecar service for Docker API access.

Provides a restricted Docker API proxy with:
- Whitelist of allowed operations (ps, inspect, logs, stats)
- Rate limiting
- Audit logging
- No privileged access to docker.sock from other containers

Run standalone:
  docker run -v /var/run/docker.sock:/var/run/docker.sock -p 2376:2376 docker-proxy

Or as a sidecar in docker-compose.
"""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import docker
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("docker-proxy")

app = FastAPI(title="Docker Proxy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
DOCKER_SOCKET = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")
RATE_LIMIT_PER_MINUTE = int(os.getenv("DOCKER_PROXY_RATE_LIMIT", "60"))
AUDIT_LOG_PATH = os.getenv("DOCKER_PROXY_AUDIT_LOG", "/var/log/docker-proxy-audit.jsonl")

# Whitelist of allowed Docker API endpoints (method, path pattern)
ALLOWED_ENDPOINTS: Set[str] = {
    "GET /containers/json",
    "GET /containers/{id}/json",
    "GET /containers/{id}/logs",
    "GET /containers/{id}/stats",
    "GET /containers/{id}/top",
    "GET /images/json",
    "GET /images/{id}/json",
    "GET /volumes",
    "GET /networks",
    "GET /info",
    "GET /version",
    "GET /_ping",
}

# Blocked operations (even if GET)
BLOCKED_CONTAINERS: Set[str] = set()

# --- State ---
_rate_counters: Dict[str, List[float]] = defaultdict(list)
_client: Optional[docker.DockerClient] = None


def get_client() -> docker.DockerClient:
    global _client
    if _client is None:
        _client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET}")
    return _client


class AuditEntry(BaseModel):
    timestamp: str
    method: str
    path: str
    client_ip: str
    status: int
    container_id: Optional[str] = None
    error: Optional[str] = None


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    window = 60.0
    _rate_counters[client_ip] = [t for t in _rate_counters[client_ip] if now - t < window]
    if len(_rate_counters[client_ip]) >= RATE_LIMIT_PER_MINUTE:
        return False
    _rate_counters[client_ip].append(now)
    return True


def _audit(entry: AuditEntry):
    try:
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(entry.json() + "\n")
    except Exception:
        pass


def _is_allowed(method: str, path: str) -> bool:
    # Allow proxy-specific endpoints without whitelist check
    if path in ("/health", "/audit/recent"):
        return True
    for pattern in ALLOWED_ENDPOINTS:
        pat_method, pat_path = pattern.split(" ", 1)
        if method != pat_method:
            continue
        # Simple pattern matching: /containers/{id}/json
        if pat_path.startswith("/containers/{id}"):
            prefix = pat_path.split("{id}")[0]
            if path.startswith(prefix):
                return True
        elif path == pat_path:
            return True
    return False


def _extract_container_id(path: str) -> Optional[str]:
    if "/containers/" in path:
        parts = path.split("/containers/")
        if len(parts) > 1:
            return parts[1].split("/")[0]
    return None


@app.get("/health")
async def health():
    try:
        client = get_client()
        client.ping()
        return {"status": "ok", "docker": "connected"}
    except Exception as e:
        return {"status": "degraded", "docker": str(e)}


@app.get("/audit/recent")
async def recent_audit(limit: int = 50):
    try:
        with open(AUDIT_LOG_PATH, "r") as f:
            lines = f.readlines()[-limit:]
        return {"entries": [json.loads(l) for l in lines if l.strip()]}
    except FileNotFoundError:
        return {"entries": []}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        return Response(content='{"error": "rate limit exceeded"}', status_code=429, media_type="application/json")
    response = await call_next(request)
    return response


@app.api_route("/{path:path}", methods=["GET"])
async def proxy_get(path: str, request: Request):
    full_path = f"/{path}"
    method = "GET"

    # Audit log
    client_ip = request.client.host if request.client else "unknown"

    if not _is_allowed(method, full_path):
        _audit(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            method=method, path=full_path, client_ip=client_ip, status=403,
            error="endpoint not in whitelist",
        ))
        raise HTTPException(status_code=403, detail="Endpoint not in whitelist")

    container_id = _extract_container_id(full_path)
    if container_id and container_id in BLOCKED_CONTAINERS:
        raise HTTPException(status_code=403, detail="Container access blocked")

    try:
        client = get_client()
        api = client.api

        # Route to Docker SDK
        if full_path == "/containers/json":
            result = api.containers(all=True)
        elif full_path.startswith("/containers/") and full_path.endswith("/json"):
            cid = container_id
            result = api.inspect_container(cid)
        elif full_path.startswith("/containers/") and "/logs" in full_path:
            cid = container_id
            logs = api.logs(cid, stdout=True, stderr=True, tail=100)
            return Response(content=logs, media_type="text/plain")
        elif full_path.startswith("/containers/") and "/stats" in full_path:
            cid = container_id
            stats = api.stats(cid, stream=False)
            return Response(content=json.dumps(stats), media_type="application/json")
        elif full_path.startswith("/containers/") and "/top" in full_path:
            cid = container_id
            result = api.top(cid)
        elif full_path == "/images/json":
            result = api.images()
        elif full_path == "/info":
            result = api.info()
        elif full_path == "/version":
            result = api.version()
        elif full_path == "/_ping":
            return Response(content="OK", media_type="text/plain")
        else:
            raise HTTPException(status_code=404, detail="Not found")

        _audit(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            method=method, path=full_path, client_ip=client_ip, status=200,
            container_id=container_id,
        ))
        return Response(
            content=json.dumps(result, default=str),
            media_type="application/json",
        )

    except docker.errors.NotFound:
        _audit(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            method=method, path=full_path, client_ip=client_ip, status=404,
            container_id=container_id, error="not found",
        ))
        raise HTTPException(status_code=404, detail="Container/image not found")
    except docker.errors.APIError as e:
        _audit(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            method=method, path=full_path, client_ip=client_ip, status=500,
            container_id=container_id, error=str(e),
        ))
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Docker proxy error")
        _audit(AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            method=method, path=full_path, client_ip=client_ip, status=500,
            container_id=container_id, error=str(e),
        ))
        raise HTTPException(status_code=500, detail="Internal proxy error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2376)
