#!/usr/bin/env python3
"""Detect recent Open WebUI assistant replies with reasoning blocks and no tool calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time


def run(cmd: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, check=False)


def main() -> int:
    lookback_sec = int(os.getenv("REASONING_LEAK_LOOKBACK_SEC", "300"))
    cutoff = time.time() - max(60, lookback_sec)
    ps = run(["docker", "ps", "--format", "{{.Names}}"])
    if ps.returncode != 0:
        print("reasoning-leak: docker unavailable", file=sys.stderr)
        return 1
    if "open-webui" not in set(ps.stdout.split()):
        print("reasoning-leak: open-webui not running; skip")
        return 0

    inspect_code = """
import sqlite3, json, time
c=sqlite3.connect('/app/backend/data/webui.db')
c.row_factory=sqlite3.Row
chat=c.execute("SELECT id, chat FROM chat ORDER BY updated_at DESC LIMIT 1").fetchone()
if not chat:
    print('{"leaks":0}')
    raise SystemExit(0)
payload=json.loads(chat['chat'] or '{}')
msgs=(payload.get('history') or {}).get('messages') or {}
items=sorted(msgs.items(), key=lambda kv: kv[1].get('timestamp', 0))
leaks=[]
for mid,m in items[-20:]:
    role=(m.get('role') or '').lower()
    content=str(m.get('content') or '')
    has_tool=bool(m.get('tool_calls'))
    ts = m.get('timestamp') or 0
    try:
        ts = float(ts)
    except Exception:
        ts = 0
    if not ts:
        # Messages without timestamp cannot be scoped to recent window reliably.
        continue
    # Support both seconds and milliseconds timestamps.
    if ts > 1e12:
        ts = ts / 1000.0
    if ts and ts < __CUTOFF__:
        continue
    if role=='assistant' and ('<details type="reasoning"' in content.lower()) and (not has_tool):
        leaks.append({'id':mid,'preview':content[:160].replace('\\n',' ')})
print(json.dumps({'leaks':len(leaks),'items':leaks}, ensure_ascii=False))
"""
    inspect_code = inspect_code.replace("__CUTOFF__", repr(cutoff))
    r = run(["docker", "exec", "-i", "open-webui", "python", "-"], stdin=inspect_code)
    if r.returncode != 0:
        print(f"reasoning-leak: inspect failed: {r.stderr.strip()}", file=sys.stderr)
        return 1
    try:
        data = json.loads((r.stdout or "{}").strip() or "{}")
    except Exception:
        print("reasoning-leak: invalid inspector output", file=sys.stderr)
        return 1

    leaks = int(data.get("leaks") or 0)
    if leaks > 0:
        print(f"reasoning-leak: DETECTED ({leaks})")
        for item in data.get("items") or []:
            print(f" - {item.get('id')}: {item.get('preview')}")
        return 2
    print("reasoning-leak: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
