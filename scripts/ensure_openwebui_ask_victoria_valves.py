#!/usr/bin/env python3
"""
Ensure Open WebUI ask_victoria tool exists with stub-safe content + proxy-safe valves.

Why:
- Open WebUI persists tools in webui.db; table can be empty after fresh volume.
- Manual UI edits or old bootstrap values can flip USE_BACKEND_PROXY=false.
- That causes raw Victoria queue/rule-fallback stubs to leak into chat responses.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

TOOL_ID = "ask_victoria_singularity_15"
TOOL_NAME = "ask_victoria"
REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "configs" / "openwebui_ask_victoria_tool.py"

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

SPECS = [
    {
        "name": "ask_victoria",
        "description": (
            "REQUIRED for any DO/ANALYZE request. Call Victoria; never invent answers "
            "from stubs/queue acks/rule-fallback."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Task or question for Victoria (required)",
                },
                "project_context": {
                    "type": "string",
                    "description": "Project context",
                    "default": "atra-web-ide",
                },
                "user_key": {
                    "type": "string",
                    "description": "Stable user id, e.g. openwebui-{user_id}",
                },
                "response_format": {
                    "type": "string",
                    "description": "text or json",
                    "default": "text",
                },
            },
            "required": ["goal"],
        },
    }
]

META = {
    "description": "Ask Victoria (Singularity 31.2+) — stub-rejecting local agent tool",
    "manifest": {"name": TOOL_NAME},
}


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def main() -> int:
    ps = run(["docker", "ps", "--format", "{{.Names}}"])
    if ps.returncode != 0:
        print("openwebui-valves: docker unavailable", file=sys.stderr)
        return 1
    names = set(line.strip() for line in ps.stdout.splitlines() if line.strip())
    if "open-webui" not in names:
        print("openwebui-valves: open-webui container not running; skip")
        return 0

    if not TOOL_PATH.is_file():
        print(f"openwebui-valves: missing tool file {TOOL_PATH}", file=sys.stderr)
        return 1

    content = TOOL_PATH.read_text(encoding="utf-8")
    if "_reject_stub_output" not in content:
        print(
            "openwebui-valves: tool file missing stub guard — abort",
            file=sys.stderr,
        )
        return 1

    user_q = run(
        [
            "docker",
            "exec",
            "open-webui",
            "python",
            "-c",
            "import sqlite3; c=sqlite3.connect('/app/backend/data/webui.db'); "
            "r=c.execute(\"SELECT id FROM user WHERE email LIKE 'admin%' LIMIT 1\").fetchone(); "
            "print(r[0] if r else '')",
        ]
    )
    user_id = (user_q.stdout or "").strip() or None
    now = int(time.time())
    payload = {
        "id": TOOL_ID,
        "user_id": user_id,
        "name": TOOL_NAME,
        "content": content,
        "specs": json.dumps(SPECS, ensure_ascii=False),
        "meta": json.dumps(META, ensure_ascii=False),
        "valves": json.dumps(DESIRED_VALVES, ensure_ascii=False),
        "updated_at": now,
        "created_at": now,
    }

    payload_host = REPO_ROOT / "scripts" / "_tmp_ask_victoria_tool_payload.json"
    installer = REPO_ROOT / "scripts" / "_tmp_openwebui_tool_upsert.py"
    payload_host.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    installer.write_text(
        """#!/usr/bin/env python3
import json, sqlite3
from pathlib import Path
data = json.loads(Path('/tmp/ask_victoria_tool_payload.json').read_text())
c = sqlite3.connect('/app/backend/data/webui.db')
row = c.execute('SELECT id FROM tool WHERE id=?', (data['id'],)).fetchone()
if row:
    c.execute(
        'UPDATE tool SET user_id=?, name=?, content=?, specs=?, meta=?, valves=?, updated_at=? WHERE id=?',
        (data['user_id'], data['name'], data['content'], data['specs'],
         data['meta'], data['valves'], data['updated_at'], data['id']),
    )
    action = 'updated'
else:
    c.execute(
        'INSERT INTO tool (id, user_id, name, content, specs, meta, valves, updated_at, created_at) '
        'VALUES (?,?,?,?,?,?,?,?,?)',
        (data['id'], data['user_id'], data['name'], data['content'], data['specs'],
         data['meta'], data['valves'], data['updated_at'], data['created_at']),
    )
    action = 'inserted'
c.commit()
chk = c.execute(
    "SELECT id, name, length(content), "
    "CASE WHEN content LIKE '%_reject_stub_output%' THEN 1 ELSE 0 END "
    "FROM tool WHERE id=?",
    (data['id'],),
).fetchone()
print(json.dumps({'action': action, 'row': list(chk) if chk else None}))
""",
        encoding="utf-8",
    )

    try:
        cp1 = run(
            ["docker", "cp", str(payload_host), "open-webui:/tmp/ask_victoria_tool_payload.json"]
        )
        cp2 = run(["docker", "cp", str(installer), "open-webui:/tmp/_tmp_openwebui_tool_upsert.py"])
        if cp1.returncode != 0 or cp2.returncode != 0:
            print(
                f"openwebui-valves: docker cp failed: {cp1.stderr} {cp2.stderr}",
                file=sys.stderr,
            )
            return 1
        exe = run(["docker", "exec", "open-webui", "python", "/tmp/_tmp_openwebui_tool_upsert.py"])
        if exe.returncode != 0:
            print(f"openwebui-valves: upsert failed: {exe.stderr.strip()}", file=sys.stderr)
            return 1
        print(f"openwebui-valves: {exe.stdout.strip()}")
        return 0
    finally:
        for p in (payload_host, installer):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
