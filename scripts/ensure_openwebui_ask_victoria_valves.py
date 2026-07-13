#!/usr/bin/env python3
"""
Ensure Open WebUI ask_victoria tool valves stay in proxy-safe mode.

Why:
- Open WebUI persists tool valves in webui.db.
- Manual UI edits or old bootstrap values can flip USE_BACKEND_PROXY=false.
- That causes raw Victoria queue statuses to leak into chat responses.
"""

from __future__ import annotations

import json
import subprocess
import sys


TOOL_ID = "ask_victoria_singularity_15"
DESIRED_VALVES = {
    "VICTORIA_URL": "http://victoria-agent:8000",
    "USE_BACKEND_PROXY": True,
    "ASK_VICTORIA_TIMEOUT": 1200,
    "BACKEND_FALLBACK_URL": "http://atra-web-ide-backend:8000",
    "HOST_WORKSPACE_PATH": "/Users/bikos/Documents/atra-web-ide",
    "CONTAINER_WORKSPACE_PATH": "/workspace/atra-web-ide",
    "BACKEND_STATUS_POLL_INTERVAL_SEC": 3,
    "BACKEND_STATUS_MAX_WAIT_SEC": 180,
    "ALWAYS_ATTACH_BIBLE_CONTEXT": True,
    "BIBLE_CONTEXT_MAX_CHARS": 4000,
    "BIBLE_MASTER_PATH": "/workspace/global_docs/MASTER_REFERENCE.md",
    "BIBLE_CHANGES_PATH": "/workspace/global_docs/CHANGES_FROM_OTHER_CHATS.md",
}


def run(cmd: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    # Check container exists/running.
    ps = run(["docker", "ps", "--format", "{{.Names}}"])
    if ps.returncode != 0:
        print("openwebui-valves: docker unavailable", file=sys.stderr)
        return 1
    names = set(line.strip() for line in ps.stdout.splitlines() if line.strip())
    if "open-webui" not in names:
        print("openwebui-valves: open-webui container not running; skip")
        return 0

    # Read current valves.
    read_code = (
        "import sqlite3; "
        "c=sqlite3.connect('/app/backend/data/webui.db'); "
        f"r=c.execute(\"SELECT valves FROM tool WHERE id='{TOOL_ID}'\").fetchone(); "
        "print(r[0] if r and r[0] else '{}')"
    )
    read = run(["docker", "exec", "open-webui", "python", "-c", read_code])
    if read.returncode != 0:
        print(f"openwebui-valves: read failed: {read.stderr.strip()}", file=sys.stderr)
        return 1
    try:
        current = json.loads((read.stdout or "{}").strip() or "{}")
    except Exception:
        current = {}

    target = dict(current)
    target.update(DESIRED_VALVES)
    if target == current:
        print("openwebui-valves: already compliant")
        return 0

    update_code = f"""
import sqlite3, json, time
tool_id = {TOOL_ID!r}
valves = json.dumps({target!r}, ensure_ascii=False)
c = sqlite3.connect('/app/backend/data/webui.db')
c.execute("UPDATE tool SET valves=?, updated_at=? WHERE id=?", (valves, int(time.time()), tool_id))
c.commit()
print("updated")
print(c.execute("SELECT valves FROM tool WHERE id=?", (tool_id,)).fetchone()[0])
"""
    up = run(["docker", "exec", "-i", "open-webui", "python", "-"], stdin=update_code)
    if up.returncode != 0:
        print(f"openwebui-valves: update failed: {up.stderr.strip()}", file=sys.stderr)
        return 1

    print("openwebui-valves: updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
