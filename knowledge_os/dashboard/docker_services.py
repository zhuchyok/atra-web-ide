"""Read-only список автономных контейнеров через docker-proxy (без docker.sock)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

AUTONOMOUS_NAME_PATTERNS = (
    r"^svc-",
    r"^sandbox-",
    r"^knowledge_os-expert-worker-",
    r"^(victoria-agent|veronica-agent)$",
    r"^(knowledge_evolution|knowledge_nightly|knowledge_os_worker|knowledge_os_orchestrator|performance-watchdog)$",
)
AUTONOMOUS_COMPOSE_TOKENS = ("expert-worker", "sandbox", "victoria-agent", "veronica-agent")
DEFAULT_PROXY_URL = "http://docker-proxy:2376"


def proxy_url() -> str:
    return (
        os.getenv("DOCKER_PROXY_URL")
        or os.getenv("DOCKER_HOST", "").replace("tcp://", "http://")
        or DEFAULT_PROXY_URL
    ).rstrip("/")


def container_name(raw: dict) -> str:
    names = raw.get("Names") or []
    if isinstance(names, list) and names:
        return str(names[0]).lstrip("/")
    return str(raw.get("Name") or "").lstrip("/")


def compose_service(raw: dict) -> str:
    labels = raw.get("Labels") or {}
    if isinstance(labels, dict):
        return str(labels.get("com.docker.compose.service") or "")
    return ""


def is_autonomous_service(name: str, compose_svc: str = "") -> bool:
    if any(re.match(pattern, name or "") for pattern in AUTONOMOUS_NAME_PATTERNS):
        return True
    return any(token in (compose_svc or "") for token in AUTONOMOUS_COMPOSE_TOKENS)


def summarize_container(raw: dict) -> dict:
    name = container_name(raw)
    image = raw.get("Image") or ""
    return {
        "name": name,
        "id": str(raw.get("Id") or "")[:12],
        "status": raw.get("Status") or raw.get("State") or "unknown",
        "state": raw.get("State") or "",
        "image": image if isinstance(image, str) else "unknown",
        "compose_service": compose_service(raw),
    }


def fetch_autonomous_services(
    base_url: str | None = None, timeout: float = 5.0
) -> tuple[list[dict], str | None]:
    """Вернуть (сервисы, ошибка). Ошибка не None — список пустой."""
    url = f"{(base_url or proxy_url()).rstrip('/')}/containers/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8") or "[]")
    except urllib.error.HTTPError as exc:
        return [], f"docker-proxy HTTP {exc.code}"
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"

    if not isinstance(payload, list):
        return [], "docker-proxy вернул не список контейнеров"

    services = [
        summarize_container(item)
        for item in payload
        if isinstance(item, dict)
        and is_autonomous_service(container_name(item), compose_service(item))
    ]
    services.sort(key=lambda item: item["name"])
    return services, None
