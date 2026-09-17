#!/usr/bin/env python3
"""Apply Open WebUI model policy for Victoria when MLX runner is unavailable."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Tuple


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = "/app/backend/data/webui.db"
MLX_URL = "http://host.docker.internal:11435"
WISDOM_MODEL = "victoria-wisdom-v3.5:latest"
SAFE_DEFAULT_MODEL = "Victoria"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def should_disable_ollama_wisdom(mlx_healthy: bool) -> bool:
    """When MLX 11435 is up, Ollama-listed wisdom is a 11434 faucet — hide it."""
    return bool(mlx_healthy)


def _mlx_brain_available() -> Tuple[bool, str]:
    """GET 11435/health only. Never generate against Ollama — that loads wisdom into 11434."""
    probe = _run(
        [
            "docker",
            "exec",
            "open-webui",
            "curl",
            "-sS",
            "-m",
            "8",
            f"{MLX_URL}/health",
        ]
    )
    body = (probe.stdout or "") + " " + (probe.stderr or "")
    low = body.lower()
    if probe.returncode != 0:
        return False, f"mlx_health_failed_rc={probe.returncode}"
    if "healthy" in low or '"status"' in low:
        return True, "mlx_11435_healthy"
    return False, "mlx_health_unexpected"


def _apply_policy(disable_wisdom: bool, reason: str) -> dict:
    state = {
        "disable_wisdom_models": disable_wisdom,
        "reason": reason,
        "default_model": SAFE_DEFAULT_MODEL,
    }
    payload = json.dumps(state, ensure_ascii=False).replace("'", "''")
    default_models = json.dumps(SAFE_DEFAULT_MODEL, ensure_ascii=False).replace("'", "''")
    wisdom_active = 0 if disable_wisdom else 1

    sql = (
        "BEGIN; "
        f"INSERT INTO config(key,value,updated_at) VALUES('ui.default_models','{default_models}',strftime('%s','now')) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at; "
        f"UPDATE model SET is_active={wisdom_active}, updated_at=strftime('%s','now') "
        "WHERE id LIKE '%victoria-wisdom%'; "
        f"INSERT INTO config(key,value,updated_at) VALUES('atra.openwebui.victoria_policy','{payload}',strftime('%s','now')) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at; "
        "COMMIT;"
    )

    apply = _run(
        [
            "docker",
            "exec",
            "open-webui",
            "python",
            "-c",
            (
                "import sqlite3; "
                f"c=sqlite3.connect('{DB_PATH}'); "
                f"c.executescript({sql!r}); "
                "rows=c.execute(\"SELECT id,is_active FROM model WHERE id LIKE '%victoria-wisdom%' ORDER BY id\").fetchall(); "
                "cfg=c.execute(\"SELECT value FROM config WHERE key='ui.default_models'\").fetchone(); "
                "print({'models':rows,'ui.default_models':(cfg[0] if cfg else None)})"
            ),
        ]
    )
    if apply.returncode != 0:
        raise RuntimeError(apply.stderr.strip() or apply.stdout.strip() or "policy apply failed")
    return {"state": state, "result": (apply.stdout or "").strip()}


def main() -> int:
    ps = _run(["docker", "ps", "--format", "{{.Names}}"])
    if ps.returncode != 0:
        print("openwebui-policy: docker unavailable", file=sys.stderr)
        return 1
    names = {line.strip() for line in (ps.stdout or "").splitlines() if line.strip()}
    if "open-webui" not in names:
        print("openwebui-policy: open-webui not running; skip")
        return 0

    ok, reason = _mlx_brain_available()
    info = _apply_policy(disable_wisdom=should_disable_ollama_wisdom(ok), reason=reason)
    print(json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
