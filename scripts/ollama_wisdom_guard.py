#!/usr/bin/env python3
"""
Гигиена слота Ollama 11434 по контракту v149.4 (библия): на 11434 живут
МОЗГ victoria-qwen38* (+qwen3.8*), РУКИ phi3.5:3.8b / nomic-embed-text (IMMORTAL
+ moondream). Всё остальное (включая victoria-wisdom* — она на MLX 11435) — выгрузить.
[v150.1] Аудит 2026-10-08: старый вариант «только phi+nomic» выгрузил мозг 1130 раз —
война с brain-keepalive. Белый список обязателен при любой смене модели мозга.
Env: WISDOM_GUARD_DRY_RUN=true — не выгружать (сухой прогон).
"""

import json
import json as _json
import os
import time
import urllib.request
from datetime import datetime

OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
POLL = int(os.getenv("WISDOM_GUARD_POLL_SEC", "60"))
DRY = os.getenv("WISDOM_GUARD_DRY_RUN", "false").lower() in ("1", "true", "yes")

# [v150.1] Контракт v149.4: мозг живёт на 11434 — никогда не выгружать.
BRAIN_ALLOW = ("victoria-qwen38", "qwen3.8")


def _log(msg: str) -> None:
    print(f"{datetime.now().strftime('%F %T')} [wisdom_guard] {msg}", flush=True)


def _ps():
    with urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=5) as r:
        return _pretty(json.loads(r.read().decode()))


def _pretty(x):
    return [(m.get("name") or "") for m in x.get("models", [])]


def unload(model):
    body = {"model": model, "keep_alive": 0}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=60).read()
    _log(f"unloaded {model} from {OLLAMA}")


def pin_phi():
    """После выгрузки wisdom слот 11434 не должен оставаться пустым.
    [v150.1] num_ctx обязателен: без опций ollama 0.33 авто-размеряет KV под
    свободную RAM → phi3.5 раздувалась до 112GB (ctx 131072) и душила хост."""
    loaded = _ps()
    if any("phi3.5:3.8b" == n or n.startswith("phi3.5:3.8b") for n in loaded):
        return
    body = {
        "model": "phi3.5:3.8b",
        "prompt": "ok",
        "stream": False,
        "keep_alive": -1,
        "options": {"num_ctx": 16384},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    # [v150.2] 240с: cold-load phi@16K занимает минуты (Metal-аллокация 15GB под
    # давлением Docker VM) — при 60с пин вечно отваливался и «спамил» err: timed out
    urllib.request.urlopen(req, timeout=240).read()
    _log(f"pinned phi3.5:3.8b on {OLLAMA}")


def pin_nomic():
    loaded = _ps()
    if any("nomic" in n for n in loaded):
        return
    body = {"model": "nomic-embed-text", "input": "ping", "keep_alive": -1}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/embed", data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=30).read()
    _log(f"pinned nomic-embed-text on {OLLAMA}")


def _should_unload(name: str) -> bool:
    """11434 = мозг (v149.4) + руки + IMMORTAL. Чужое (wisdom на MLX, тяжёлые гости) — выгрузить."""
    key = (name or "").lower()
    if not key:
        return False
    if "nomic" in key or "moondream" in key:
        return False
    if key.startswith("phi3.5:3.8b"):
        return False
    if any(b in key for b in BRAIN_ALLOW):
        return False
    return True


def _enforce_hands_slot():
    names = _ps()
    evict = [n for n in names if _should_unload(n)]
    if evict:
        _log(f"evict from {OLLAMA}: {evict}")
        if not DRY:
            for n in evict:
                unload(n)
        else:
            _log(f"dry-run unload skipped: {evict}")
    if not DRY:
        pin_phi()
        pin_nomic()
    left = _ps()
    _log(f"ok: {OLLAMA} api/ps={left}")


while True:
    try:
        _enforce_hands_slot()
    except Exception as e:
        _log(f"err: {e}")
    time.sleep(POLL)
