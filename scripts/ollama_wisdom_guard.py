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


while True:
    try:
        names = [n for n in _ps() if "wisdom" in n.lower()]
        if names:
            print(f"[wisdom_guard] detected: {names}", flush=True)
            if not DRY:
                for n in names:
                    unload(n)
            else:
                print(f"[wisdom_guard] dry-run unload skipped: {names}", flush=True)
        else:
            print(f"[wisdom_guard] ok: wisdom not in {OLLAMA} api/ps", flush=True)
    except Exception as e:
        print(f"[wisdom_guard] err: {e}", flush=True)
    time.sleep(POLL)
