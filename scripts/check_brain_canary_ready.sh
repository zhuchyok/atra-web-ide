#!/bin/bash
# List victoria-qwen38* tags on 11434 and whether :canary exists.
# Does not pull or unload. Read-only.
set -euo pipefail
U="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
TAGS=$(curl -s --max-time 10 "$U/api/tags" || true)
if [ -z "$TAGS" ]; then
  echo "11434: unreachable ($U)"
  exit 1
fi
echo "qwen38 tags on $U:"
echo "$TAGS" | VICTORIA_BRAIN_MODEL="${VICTORIA_BRAIN_MODEL-}" /usr/bin/python3 -c '
import json, os, sys
data = json.load(sys.stdin)
names = sorted(m.get("name") or "" for m in data.get("models", []))
q = [n for n in names if "qwen38" in n.lower()]
for n in q:
    print(f"  {n}")
if not q:
    print("  (none)")
canary = any("qwen38" in n and n.endswith(":canary") for n in q)
print(f"canary_exists={canary}")
env = os.environ.get("VICTORIA_BRAIN_MODEL") or "(unset → victoria-qwen38:latest)"
print(f"VICTORIA_BRAIN_MODEL={env}")
'
