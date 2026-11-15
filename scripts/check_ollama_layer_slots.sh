#!/usr/bin/env bash
# Live fail-closed check for MASTER layer slots (VRAM /api/ps, not tags inventory).
# Brain 11434: victoria-qwen38*
# Hands 11437: XOR exactly one phi3.5* + nomic*
# Coder 11436: only qwen3-coder*

set -euo pipefail
FAIL=0

json_ps() {
  local port="$1"
  curl -sf --connect-timeout 3 "http://127.0.0.1:${port}/api/ps" || {
    echo "❌ Ollama :${port} /api/ps unavailable"
    return 1
  }
}

echo "=== Layer slot check (loaded models) ==="

# Brain
BRAIN_JSON="$(json_ps 11434)" || FAIL=1
if [ "$FAIL" -eq 0 ]; then
  python3 - "$BRAIN_JSON" <<'PY' || FAIL=1
import json,sys
names=[m.get("name","") for m in json.loads(sys.argv[1]).get("models",[])]
ok=bool(names) and all("victoria-qwen38" in n for n in names) and not any(
  x in n for n in names for x in ("phi","nomic","wisdom","minicpm","coder")
)
print("11434 loaded:", names)
print("✅ brain" if ok else "❌ brain: expect only victoria-qwen38*")
sys.exit(0 if ok else 1)
PY
fi

# Hands
HANDS_JSON="$(json_ps 11437)" || FAIL=1
if [ -n "${HANDS_JSON:-}" ]; then
  python3 - "$HANDS_JSON" <<'PY' || FAIL=1
import json,sys
names=[m.get("name","") for m in json.loads(sys.argv[1]).get("models",[])]
phis=[n for n in names if "phi3.5" in n]
noms=[n for n in names if "nomic" in n]
stray=[n for n in names if n and "phi3.5" not in n and "nomic" not in n]
ok=len(phis)==1 and len(noms)>=1 and not stray
print("11437 loaded:", names)
print("✅ hands XOR" if ok else "❌ hands: need exactly 1 phi + nomic, no stray")
sys.exit(0 if ok else 1)
PY
fi

# Coder
CODER_JSON="$(json_ps 11436)" || FAIL=1
if [ -n "${CODER_JSON:-}" ]; then
  python3 - "$CODER_JSON" <<'PY' || FAIL=1
import json,sys
names=[m.get("name","") for m in json.loads(sys.argv[1]).get("models",[])]
ok=len(names)==1 and any("qwen3-coder:30b" in n for n in names)
print("11436 loaded:", names)
print("✅ coder solo" if ok else "❌ coder: expect only qwen3-coder:30b loaded")
sys.exit(0 if ok else 1)
PY
fi

echo "=============================="
if [ "$FAIL" -eq 0 ]; then
  echo "✅ Layer slots OK"
else
  echo "⚠️ Layer slots FAILED"
fi
exit "$FAIL"
