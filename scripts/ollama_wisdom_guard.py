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
import subprocess
import time
import urllib.request
from datetime import datetime

OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
# [v150.8] Руки живут на выделенном инстансе 11437 (свой планировщик)
HANDS = os.getenv("OLLAMA_HANDS_URL", "http://127.0.0.1:11437").rstrip("/")
CODER = os.getenv("OLLAMA_CODER_URL", "http://127.0.0.1:11436").rstrip("/")
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


def _should_pin_phi(loaded) -> bool:
    """[v150.76] Любой phi (base или -stable) = слот рук занят.
    Точный тег грузил второй 9–16GB поверх stable → HTTP 500 / выселял nomic."""
    return not any("phi3.5" in (n or "") for n in (loaded or []))


def pin_phi():  # [v150.8] пин на инстансе рук (11437)
    """После выгрузки wisdom слот 11434 не должен оставаться пустым.
    [v150.1] num_ctx обязателен: без опций ollama 0.33 авто-размеряет KV под
    свободную RAM → phi3.5 раздувалась до 112GB (ctx 131072) и душила хост.
    [v150.10] Точное сравнение тегов: '-stable'.startswith('phi3.5:3.8b')
    ломало проверку (базовая phi считалась загруженной)."""
    loaded = _ps(HANDS)
    if not _should_pin_phi(loaded):
        return
    body = {
        "model": "phi3.5:3.8b",
        "prompt": "ok",
        "stream": False,
        "keep_alive": -1,
        # [v150.76] 8192 не 16384: 16k×4 parallel = 16GB KV, Ollama выселяет nomic.
        "options": {"num_ctx": 8192},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HANDS}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    # [v150.2] 240с: cold-load phi занимает минуты (Metal под давлением Docker VM) —
    # при 60с пин вечно отваливался и «спамил» err: timed out
    urllib.request.urlopen(req, timeout=240).read()
    _log(f"pinned phi3.5:3.8b on {HANDS}")


def _should_pin_stable(loaded) -> bool:
    """[v150.73] Второй phi (stable) не грузим, если на руках уже есть базовый.
    Иначе pin_stable держит гвард 120с, не доходит до гигиены 11436 и давит мозг."""
    names = loaded or []
    if not names:
        return False
    if any(n.startswith("phi3.5:3.8b-stable") for n in names):
        return False
    if any("phi3.5" in (n or "") for n in names):
        return False
    return True


def pin_stable():  # [v150.10] факт-полоса: -stable — отдельный раннер, никто
    # кроме факт-фаст-трека её не занимает; без пина выселялась при рестартах
    # инстанса → факты теряли свои 4-9с. Лёгкая аллокация: ctx 2048.
    loaded = _ps(HANDS)
    if not _should_pin_stable(loaded):
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


_PIN_NOMIC_FAIL_AT = 0.0
_PIN_NOMIC_BACKOFF_SEC = int(os.getenv("WISDOM_GUARD_NOMIC_BACKOFF_SEC", "900"))


def _should_pin_nomic(loaded) -> bool:
    """[v150.76] Пин только если nomic нет в /api/ps."""
    return not any("nomic" in (n or "") for n in (loaded or []))


def _nomic_backoff_active(now=None) -> bool:
    """[v150.76] После timeout не класть ещё один hung /api/embed — Ollama не отменяет load."""
    t = now if now is not None else time.time()
    return (t - _PIN_NOMIC_FAIL_AT) < _PIN_NOMIC_BACKOFF_SEC


def pin_nomic():  # [v150.8] пин на инстансе рук (11437)
    global _PIN_NOMIC_FAIL_AT
    loaded = _ps(HANDS)
    if not _should_pin_nomic(loaded):
        return
    if _nomic_backoff_active():
        _log("pin_nomic skip: backoff after timeout")
        return
    body = {"model": "nomic-embed-text", "input": "ping", "keep_alive": -1}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HANDS}/api/embed", data=data, headers={"Content-Type": "application/json"}
    )
    # [v150.76] 240с как pin_phi: cold-load рядом с phi@16K не укладывается в 30с.
    # Client timeout не отменяет runner — 30с каждые 60с копило hung embed.
    try:
        urllib.request.urlopen(req, timeout=240).read()
    except Exception:
        _PIN_NOMIC_FAIL_AT = time.time()
        raise
    _log(f"pinned nomic-embed-text on {HANDS}")


HANDS_ALLOW = ("phi3.5", "nomic", "smollm", "tinyllama", "moondream")
CODER_ALLOW = ("qwen3-coder", "qwen2.5-coder")


def unload_hands(model):
    body = {"model": model, "keep_alive": 0}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HANDS}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=240).read()
    _log(f"unloaded {model} from {HANDS}")


def _should_unload_hands(name: str) -> bool:
    """[v150.13] 11437 = только руки (симметрия brain-only@11434). Утром 15.10
    мозг грузился на инстансе рук — вытеснял phi, RAM падала до 29%."""
    key = (name or "").lower()
    if not key:
        return False
    return not any(a in key for a in HANDS_ALLOW)


def _should_pin_brain(loaded) -> bool:
    """[v150.73] Пустой 11434 = дыра в контракте. brain-keepalive выключен — пин здесь."""
    return not any(
        any(b in (n or "").lower() for b in BRAIN_ALLOW) for n in (loaded or [])
    )


def _brain_runner_alive() -> bool:
    """[v150.84] /api/ps может держать ghost: имя есть, llama-server нет. Generate тогда висит до GIN."""
    try:
        out = subprocess.check_output(["ps", "aux"], timeout=5, text=True)
    except Exception:
        return True
    return any(
        "llama-server" in ln and "ollama-brain" in ln for ln in out.splitlines()
    )


def _ghost_hits_path() -> str:
    d = os.getenv("ATRA_RUNTIME_STATE_DIR", "/tmp/atra_runtime_state")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "brain_ghost_hits")


def _note_brain_ghost() -> int:
    path = _ghost_hits_path()
    try:
        hits = int((open(path, encoding="utf-8").read() or "0").strip() or "0")
    except Exception:
        hits = 0
    hits += 1
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(str(hits))
    except Exception:
        pass
    return hits


def _clear_brain_ghost() -> None:
    try:
        os.remove(_ghost_hits_path())
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _kickstart_brain_serve() -> None:
    uid = os.getuid()
    subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{uid}/homebrew.mxcl.ollama"],
        check=False,
        timeout=15,
    )


def pin_brain():
    loaded = _ps()
    if not _should_pin_brain(loaded):
        if not _brain_runner_alive():
            hits = _note_brain_ghost()
            _log(
                f"GHOST brain in /api/ps without llama-server (hit={hits}) — skip generate (would hang)"
            )
            # Two consecutive polls (~2 min) before kickstart, so a cold load is not killed.
            if hits >= 2 and not DRY:
                _log("GHOST — kickstart only 11434")
                _kickstart_brain_serve()
                _clear_brain_ghost()
        else:
            _clear_brain_ghost()
        return
    body = {
        "model": "victoria-qwen38:latest",
        "prompt": "ok",
        "stream": False,
        # [v150.76] keep_alive=-1 на 11434 не держит runner (ps пустеет сразу
        # после generate). "24h" оставляет victoria-qwen38 в /api/ps.
        "keep_alive": "24h",
        "options": {"num_predict": 1, "num_ctx": 16384},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=240).read()
    _log(f"pinned victoria-qwen38:latest on {OLLAMA}")


def _should_unload(name: str) -> bool:
    """[v150.8] 11434 = ТОЛЬКО мозг (v149.4). Руки/эмбеддер/прочее — на 11437,
    их присутствие здесь = чужой слот (конкуренция за память с мозгом)."""
    key = (name or "").lower()
    if not key:
        return False
    return not any(b in key for b in BRAIN_ALLOW)


def _should_unload_coder(name: str) -> bool:
    """[v150.73] 11436 = только coder. phi/nomic/мозг на этом порту = чужой слот."""
    key = (name or "").lower()
    if not key:
        return False
    return not any(a in key for a in CODER_ALLOW)


def unload_coder(model):
    body = {"model": model, "keep_alive": 0}
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{CODER}/api/generate", data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=60).read()
    _log(f"unloaded {model} from {CODER}")


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
        for fn, label in (
            (pin_brain, "pin_brain"),
            (pin_nomic, "pin_nomic"),
            (pin_phi, "pin_phi"),
            (pin_stable, "pin_stable"),
        ):
            try:
                fn()
            except Exception as e:
                _log(f"{label} skip: {e}")
    left = _ps()
        # [v150.13] гигиена 11437: не-руки (например мозг-утечка) — выгрузить
    try:
        _stray = [n for n in _ps(HANDS) if _should_unload_hands(n)]
        if _stray:
            _log(f"evict from {HANDS} (не-руки): {_stray}")
            # [v149.63] ntfy-алерт: мозг на руках = клиент-утечка, ловим живьём
            try:
                import urllib.request as _ur
                _msg = f"ATRA: на руках {HANDS} обнаружен не-руки: {_stray} — ищи клиент-утечку (brain-модель на hands-URL)"
                _ur.urlopen(_ur.Request(
                    "https://ntfy.sh/atra_victoria_curator",
                    data=_msg.encode(), headers={"Title": "🔴 Утечка модели на hands", "Priority": "high"},
                ), timeout=8)
            except Exception:
                pass
            if not DRY:
                for _n in _stray:
                    unload_hands(_n)
    except Exception as _e:
        _log(f"hands-hygiene err: {_e}")

    try:
        stray_coder = [n for n in _ps(CODER) if _should_unload_coder(n)]
        if stray_coder:
            _log(f"evict from {CODER} (не-coder): {stray_coder}")
            if not DRY:
                for _n in stray_coder:
                    unload_coder(_n)
    except Exception as _e:
        _log(f"coder-hygiene err: {_e}")

    _log(f"ok: brain{OLLAMA}={left} hands{HANDS}={_ps(HANDS)} coder{CODER}={_ps(CODER)}")


if __name__ == "__main__":
    while True:
        try:
            _enforce_hands_slot()
        except Exception as e:
            _log(f"err: {e}")
        time.sleep(POLL)
