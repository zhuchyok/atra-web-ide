#!/usr/bin/env bash
# One-shot: if pull+create done → NIGHT (opt-in). Else print status.
# Usage: bash scripts/brain_night_120b_go.sh           # status
#        AUTO_NIGHT=1 bash scripts/brain_night_120b_go.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "== night-120b go =="
if ! ollama list 2>/dev/null | grep -q 'gpt-oss:120b'; then
  echo "WAIT: gpt-oss:120b not in ollama list yet"
  grep 'HB ' "$ROOT/logs/night_120b_pipeline.log" 2>/dev/null | tail -2 || true
  exit 2
fi
if ! ollama list 2>/dev/null | grep -q 'victoria-night:120b'; then
  echo "CREATE victoria-night:120b"
  OLLAMA_HOST=127.0.0.1:11434 ollama create victoria-night:120b \
    -f "$ROOT/configs/models/Modelfile.victoria-night-120b"
fi
bash "$ROOT/scripts/brain_night_120b_window.sh" PRECHECK
if [ "${AUTO_NIGHT:-0}" != "1" ]; then
  echo "PRECHECK done. Set AUTO_NIGHT=1 to run NIGHT (unload→battle; free target ≥20GB)."
  echo "Morning: bash scripts/brain_night_120b_window.sh ROLLBACK"
  exit 0
fi
bash "$ROOT/scripts/brain_night_120b_window.sh" NIGHT
echo "NIGHT finished. Morning: bash scripts/brain_night_120b_window.sh ROLLBACK"
