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
# [v150.8] Руки живут на выделенном инстансе 11437 (свой планировщик)
HANDS = os.getenv("OLLAMA_HANDS_URL", "http://127.0.0.1:11437").rstrip("/")
POLL = int(os.getenv("WISDOM_GUARD_POLL_SEC", "60"))
DRY = os.getenv("WISDOM_GUARD_DRY_RUN", "false").lower() in ("1", "true", "yes")

# [v150.1] Контракт v149.4: мозг живёт на 11434 — никогда не выгружать.
# [v150.8] На 11434 живёт ТОЛЬКО мозг: руки/эмбеддер переехали на 11437 —
# их присутствие на 11434 = чужой слот, выгружать.
BRAIN_ALLOW = ("victoria-qwen38", "qwen3.8")


def _log(msg: str) -> None:
    print(f"{datetime.now().strftime('%F %T')} [wisdom_guard] {msg}", flush=True)


def _ps(base=None):
    with urllib.request.urlopen(f"{base or OLLAMA}/api/ps", timeout=5) as r:
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


def pin_phi():  # [v150.8] пин на инстансе рук (11437)
    """После выгрузки wisdom слот 11434 не должен оставаться пустым.
    [v150.1] num_ctx обязателен: без опций ollama 0.33 авто-размеряет KV под
    свободную RAM → phi3.5 раздувалась до 112GB (ctx 131072) и душила хост.
    [v150.10] Точное сравнение тегов: '-stable'.startswith('phi3.5:3.8b')
    ломало проверку (базовая phi считалась загруженной)."""
    loaded = _ps(HANDS)
    if any(n in ("phi3.5:3.8b", "phi3.5:3.8b:latest") for n in loaded):
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
        f"{HANDS}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    # [v150.2] 240с: cold-load phi@16K занимает минуты (Metal-аллокация 15GB под
    # давлением Docker VM) — при 60с пин вечно отваливался и «спамил» err: timed out
    urllib.request.urlopen(req, timeout=240).read()
    _log(f"pinned phi3.5:3.8b on {HANDS}")


def pin_stable():  # [v150.10] факт-полоса: -stable — отдельный раннер, никто
    # кроме факт-фаст-трека её не занимает; без пина выселялась при рестартах
    # инстанса → факты теряли свои 4-9с. Лёгкая аллокация: ctx 2048.
    loaded = _ps(HANDS)
    if any(n.startswith("phi3.5:3.8b-stable") for n in loaded):
        return
    body = {
        "model": "phi3.5:3.8b-stable",
        "prompt": "ok",
        "stream": False,
        "keep_alive": -1,
        "options": {"num_ctx": 2048, "num_predict": 1},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HANDS}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=120).read()
    _log(f"pinned phi3.5:3.8b-stable (факт-полоса) on {HANDS}")


def pin_nomic():  # [v150.8] пин на инстансе рук (11437)
    loaded = _ps(HANDS)
    if any("nomic" in n for n in loaded):
        return
    body = {"model": "nomic-embed-text", "input": "ping", "keep_alive": -1}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HANDS}/api/embed", data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=30).read()
    _log(f"pinned nomic-embed-text on {HANDS}")


def _should_unload(name: str) -> bool:
    """[v150.8] 11434 = ТОЛЬКО мозг (v149.4). Руки/эмбеддер/прочее — на 11437,
    их присутствие здесь = чужой слот (конкуренция за память с мозгом)."""
    key = (name or "").lower()
    if not key:
        return False
    return not any(b in key for b in BRAIN_ALLOW)


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
        pin_stable()
        pin_nomic()
    left = _ps()
    _log(f"ok: brain{OLLAMA}={left} hands{HANDS}={_ps(HANDS)}")


while True:
    try:
        _enforce_hands_slot()
    except Exception as e:
        _log(f"err: {e}")
    time.sleep(POLL)
