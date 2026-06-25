#!/usr/bin/env python3
"""Auto-sync Open WebUI model policy when Ollama model list changes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = ROOT / ".tmp"
PID_FILE = TMP_DIR / "openwebui_model_policy_watcher.pid"
STATE_FILE = TMP_DIR / "openwebui_model_policy_watcher.state.json"
POLICY_SCRIPT = ROOT / "scripts" / "ensure_openwebui_victoria_policy.py"
VALVES_SCRIPT = ROOT / "scripts" / "ensure_openwebui_ask_victoria_valves.py"


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)


def _log(msg: str) -> None:
    print(f"[openwebui-policy-watcher] {msg}", flush=True)


def _is_pid_alive(pid: int) -> bool:
    if pid <= 1:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _acquire_pid_file() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text(encoding="utf-8").strip() or "0")
        except Exception:
            old_pid = 0
        if _is_pid_alive(old_pid):
            _log(f"already running (pid={old_pid}), exiting")
            raise SystemExit(0)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _cleanup_pid_file(*_: object) -> None:
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


def _docker_ready() -> bool:
    cp = _run(["docker", "ps", "--format", "{{.Names}}"], timeout=15)
    if cp.returncode != 0:
        return False
    names = {line.strip() for line in cp.stdout.splitlines() if line.strip()}
    return "open-webui" in names


def _ollama_signature() -> Optional[str]:
    cp = _run(["ollama", "list"], timeout=30)
    if cp.returncode != 0:
        return None
    lines = []
    for idx, line in enumerate((cp.stdout or "").splitlines()):
        s = (line or "").strip()
        if not s:
            continue
        if idx == 0 and "NAME" in s and "ID" in s:
            continue
        lines.append(s)
    payload = "\n".join(sorted(lines))
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_once(force: bool = False) -> bool:
    if not _docker_ready():
        _log("docker/open-webui not ready, skip")
        return False
    sig = _ollama_signature()
    if sig is None:
        _log("ollama list unavailable, skip")
        return False
    state = _load_state()
    prev_sig = str(state.get("ollama_signature") or "")
    if not force and prev_sig == sig:
        return False

    _log("model set changed; applying valves + policy")
    v = _run([sys.executable, str(VALVES_SCRIPT)], timeout=120)
    if v.returncode != 0:
        _log(f"valves sync failed: {v.stderr.strip()[:300]}")
        return False
    p = _run([sys.executable, str(POLICY_SCRIPT)], timeout=240)
    if p.returncode != 0:
        _log(f"policy sync failed: {p.stderr.strip()[:300]}")
        return False
    state["ollama_signature"] = sig
    state["updated_at"] = int(time.time())
    _save_state(state)
    _log("sync applied successfully")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-apply Open WebUI model policy on Ollama changes")
    parser.add_argument("--once", action="store_true", help="Run one sync check and exit")
    parser.add_argument("--force", action="store_true", help="Force sync even without signature change")
    parser.add_argument(
        "--interval-sec",
        type=int,
        default=int(os.getenv("OPENWEBUI_POLICY_WATCH_INTERVAL_SEC", "86400")),
        help="Polling interval in seconds",
    )
    args = parser.parse_args()

    _acquire_pid_file()
    signal.signal(signal.SIGTERM, _cleanup_pid_file)
    signal.signal(signal.SIGINT, _cleanup_pid_file)

    try:
        _sync_once(force=args.force)
        if args.once:
            return 0
        interval = max(300, int(args.interval_sec))
        _log(f"started (interval={interval}s)")
        while True:
            time.sleep(interval)
            _sync_once(force=False)
    finally:
        _cleanup_pid_file()


if __name__ == "__main__":
    raise SystemExit(main())
