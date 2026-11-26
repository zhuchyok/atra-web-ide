#!/usr/bin/env bash
# brain_canary_window.sh — NEXT canary replay AFTER baseline v2 finishes.
# Win rule: promote only if Δ pass ≥ 2/20 vs baseline v2.
# Harness v2: brain_canary_battle.py (chat-only + nonce echo + must_pass/forbid).
# Live pin: victoria-qwen38:latest @11434. Canary tag: victoria-qwen38:canary.
# Compose recreate: knowledge_os/docker-compose.yml + docker-compose.agents.yml.
# CANARY: unload :latest → load :canary@16384 stream:false → recreate → battle.
# ROLLBACK: unload :canary → pin :latest@16384 → recreate with :latest.
# Refuse CANARY if /api/ps already has dual qwen38 brains. No auto-promote.
# Usage: bash scripts/brain_canary_window.sh {PRECHECK|CANARY|ROLLBACK}
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OLLAMA="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
VICTORIA_URL="${VICTORIA_URL:-http://127.0.0.1:8010}"
LIVE="victoria-qwen38:latest"
CANARY="victoria-qwen38:canary"
COMPOSE=(docker compose
  -f "$ROOT/knowledge_os/docker-compose.yml"
  -f "$ROOT/knowledge_os/docker-compose.agents.yml")

usage() {
  cat <<EOF
Usage: $0 {PRECHECK|CANARY|ROLLBACK}

  PRECHECK  canary tag exists, live is :latest, victoria health ok
  CANARY    unload latest → load canary@16384 → recreate victoria-agent → battle
  ROLLBACK  unload canary → pin latest → recreate victoria-agent :latest

Win: Δ pass ≥ 2/20 (harness v2 nonce+forbid). Do not promote automatically.
EOF
}

tag_exists() {
  local want="$1"
  curl -sf --max-time 10 "$OLLAMA/api/tags" | /usr/bin/python3 -c '
import json,sys
want=sys.argv[1]
names={m.get("name") or "" for m in json.load(sys.stdin).get("models",[])}
# ollama may omit :latest
alts={want, want.replace(":latest","")} if want.endswith(":latest") else {want}
sys.exit(0 if names & alts else 1)
' "$want"
}

victoria_health_ok() {
  curl -sf --max-time 8 "$VICTORIA_URL/health" >/dev/null
}

# Distinct victoria-qwen38* runners currently resident in /api/ps
ps_qwen38_brains() {
  curl -sf --max-time 8 "$OLLAMA/api/ps" | /usr/bin/python3 -c '
import json,sys
names=sorted({(m.get("name") or "") for m in json.load(sys.stdin).get("models",[])
              if "qwen38" in (m.get("name") or "").lower()})
print("\n".join(names))
'
}

dual_brains() {
  local n
  n="$(ps_qwen38_brains | grep -c . || true)"
  [ "${n:-0}" -ge 2 ]
}

unload_model() {
  local model="$1"
  echo "==> unload $model (keep_alive=0)"
  curl -sf --max-time 120 "$OLLAMA/api/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$model\",\"prompt\":\".\",\"stream\":false,\"keep_alive\":0}" >/dev/null \
    || echo "WARN: unload $model returned non-zero (may already be cold)"
}

load_brain() {
  local model="$1"
  echo "==> load $model @16384 stream:false think:false"
  curl -sf --max-time 600 "$OLLAMA/api/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$model\",\"prompt\":\"ok\",\"stream\":false,\"think\":false,\"keep_alive\":\"24h\",\"options\":{\"num_predict\":8,\"num_ctx\":16384}}" >/dev/null
  # Fail closed: empty /api/ps after "success" already bit us once.
  local i names
  for i in 1 2 3 4 5 6 7 8 9 10; do
    names="$(ps_qwen38_brains || true)"
    if echo "$names" | grep -qx "$model"; then
      echo "ok: resident $model"
      # drop sibling qwen38 if dual
      if dual_brains; then
        echo "WARN: dual brains — unloading siblings except $model"
        while IFS= read -r other; do
          [ -z "$other" ] && continue
          [ "$other" = "$model" ] && continue
          unload_model "$other"
        done <<< "$names"
      fi
      return 0
    fi
    sleep 1
  done
  echo "ERROR: $model not in /api/ps after load" >&2
  ps_qwen38_brains >&2 || true
  return 1
}

recreate_victoria() {
  local model="$1"
  echo "==> recreate victoria-agent with $model"
  (
    cd "$ROOT"
    export VICTORIA_BRAIN_MODEL="$model"
    export VICTORIA_MODEL="$model"
    export VICTORIA_PLANNER_MODEL="$model"
    export VICTORIA_STRATEGIST_MODEL="$model"
    export VICTORIA_EXECUTOR_MODEL="$model"
    export VICTORIA_SYNC_SAFE_MODEL="$model"
    export VICTORIA_TIMEOUT_FALLBACK_MODEL="$model"
    "${COMPOSE[@]}" up -d --force-recreate --no-deps victoria-agent
  )
  # brief health wait
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if victoria_health_ok; then
      echo "victoria health ok"
      return 0
    fi
    sleep 2
  done
  echo "ERROR: victoria health not ok after recreate" >&2
  return 1
}

cmd_precheck() {
  echo "== PRECHECK =="
  if ! curl -sf --max-time 5 "$OLLAMA/api/tags" >/dev/null; then
    echo "FAIL: 11434 unreachable ($OLLAMA)"; exit 1
  fi
  if ! tag_exists "$CANARY"; then
    echo "FAIL: missing tag $CANARY"; exit 1
  fi
  echo "ok: $CANARY present"
  if ! tag_exists "$LIVE"; then
    echo "FAIL: missing live tag $LIVE"; exit 1
  fi
  echo "ok: live tag $LIVE present"
  if ! victoria_health_ok; then
    echo "FAIL: victoria health ($VICTORIA_URL/health)"; exit 1
  fi
  echo "ok: victoria health"
  echo "resident qwen38 brains:"
  ps_qwen38_brains | sed 's/^/  /' || echo "  (none)"
  if dual_brains; then
    echo "WARN: dual qwen38 brains already resident — CANARY will refuse"
  fi
  echo "PRECHECK ok"
}

cmd_canary() {
  local mode="${2:-ollama}"  # ollama|victoria
  echo "== CANARY window (mode=$mode) =="
  cmd_precheck
  if dual_brains; then
    echo "REFUSE: /api/ps already has dual qwen38 brains — unload one first" >&2
    ps_qwen38_brains >&2
    exit 2
  fi
  unload_model "$LIVE"
  load_brain "$CANARY"
  if [ "$mode" = "victoria" ]; then
    recreate_victoria "$CANARY"
    echo "==> victoria battle --model-label canary"
    python3 "$ROOT/scripts/brain_canary_battle.py" --model-label canary
  else
    echo "==> ollama-direct battle (no victoria recreate)"
    python3 "$ROOT/scripts/brain_canary_ollama_direct.py" \
      --model "$CANARY" --model-label canary
  fi
  echo "CANARY battle done. Review Δ pass ≥ 2/20, then ROLLBACK (or promote manually)."
}

cmd_rollback() {
  echo "== ROLLBACK =="
  unload_model "$CANARY"
  load_brain "$LIVE"
  recreate_victoria "$LIVE"
  echo "ROLLBACK done — pinned $LIVE"
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    PRECHECK) cmd_precheck ;;
    CANARY)   cmd_canary "$@" ;;
    ROLLBACK) cmd_rollback ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
