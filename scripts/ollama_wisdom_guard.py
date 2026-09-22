#!/usr/bin/env python3
"""
[4.2-QUALITY] Wisdom не должен сидеть в Ollama 11434 (она живёт на MLX 11435).
Каждые POLL_SEC: GET /api/ps → если найдена victoria-wisdom* → POST /api/generate keep_alive=0 (выгрузить) + лог.
Дедуп не нужен (unload идемпотентен). Env: WISDOM_GUARD_DRY_RUN座谈ры запрет.
"""
import os, time, urllib.request, json as _json, json

OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
POLL = int(os.getenv("WISDOM_GUARD_POLL_SEC", "60"))
DRY = os.getenv("WISDOM_GUARD_DRY_RUN", "false").lower() in ("1","true","yes")


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
    urllib.request.urlopen(req, timeout=15).read()
    print(f"[wisdom_guard] unloaded {model} from {OLLAMA}", flush=True)


def pin_phi():
    """После выгрузки wisdom слот 11434 не должен оставаться пустым."""
    loaded = _ps()
    if any("phi3.5:3.8b" == n or n.startswith("phi3.5:3.8b") for n in loaded):
        return
    body = {
        "model": "phi3.5:3.8b",
        "prompt": "ok",
        "stream": False,
        "keep_alive": -1,
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=60).read()
    print(f"[wisdom_guard] pinned phi3.5:3.8b on {OLLAMA}", flush=True)


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
    print(f"[wisdom_guard] pinned nomic-embed-text on {OLLAMA}", flush=True)


def _should_unload(name: str) -> bool:
    key = (name or "").lower()
    return "wisdom" in key or "minicpm" in key or "smollm" in key


def _enforce_hands_slot():
    names = _ps()
    evict = [n for n in names if _should_unload(n)]
    if evict:
        print(f"[wisdom_guard] evict from {OLLAMA}: {evict}", flush=True)
        if not DRY:
            for n in evict:
                unload(n)
        else:
            print(f"[wisdom_guard] dry-run unload skipped: {evict}", flush=True)
    if not DRY:
        pin_phi()
        pin_nomic()
    left = _ps()
    print(f"[wisdom_guard] ok: {OLLAMA} api/ps={left}", flush=True)


while True:
    try:
        _enforce_hands_slot()
    except Exception as e:
        print(f"[wisdom_guard] err: {e}", flush=True)
    time.sleep(POLL)
