#!/usr/bin/env bash
# brain_night_120b_window.sh — night-only gpt-oss-120B playbook (expert v173).
# Day live pin stays victoria-qwen38:latest @11434. No auto-promote.
# Fit rule: 120B + coder/MLX/hands does NOT fit ~128GB unified — unload first.
# Battle first via ollama-direct; Victoria recreate only with FORCE_VICTORIA=1.
# Usage: bash scripts/brain_night_120b_window.sh {PRECHECK|PULL_HINT|NIGHT|ROLLBACK}
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OLLAMA="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
VICTORIA_URL="${VICTORIA_URL:-http://127.0.0.1:8010}"
CODER_URL="${OLLAMA_CODER_URL:-http://127.0.0.1:11436}"
HANDS_URL="${OLLAMA_HANDS_URL:-http://127.0.0.1:11437}"
MLX_URL="${MLX_BASE_URL:-http://127.0.0.1:11435}"
LIVE="victoria-qwen38:latest"
BASE_WEIGHTS="${NIGHT_120B_BASE:-gpt-oss:120b}"
NIGHT_TAG="${NIGHT_120B_TAG:-victoria-night:120b}"
# Local hour window (host TZ). Override with NIGHT_HOUR_START/END.
NIGHT_START="${NIGHT_HOUR_START:-23}"
NIGHT_END="${NIGHT_HOUR_END:-6}"
COMPOSE=(docker compose
  -f "$ROOT/knowledge_os/docker-compose.yml"
  -f "$ROOT/knowledge_os/docker-compose.agents.yml")

usage() {
  cat <<EOF
Usage: $0 {PRECHECK|PULL_HINT|NIGHT|ROLLBACK}

  PRECHECK   tags/health/night-window/RAM hint — never loads 120B
  PULL_HINT  print manual pull + create commands (no network)
  NIGHT      unload MLX→coder→hands→live → load $NIGHT_TAG → ollama-direct battle
  ROLLBACK   unload night → pin $LIVE @16384 → restore victoria-agent

Env:
  FORCE_NIGHT=1              allow NIGHT outside hour window (still no auto-promote)
  FORCE_VICTORIA=1           also recreate victoria-agent on $NIGHT_TAG (dangerous)
  ALLOW_NIGHT_WITH_DOCKER=1  allow NIGHT while Docker Desktop is up (often OOMs)
  FORCE_LOW_FREE=1           allow load if free after unload still <20GB
  NIGHT_120B_BASE            default gpt-oss:120b
  NIGHT_120B_TAG             default victoria-night:120b
EOF
}

tag_exists() {
  local want="$1" url="${2:-$OLLAMA}"
  curl -sf --max-time 10 "$url/api/tags" | /usr/bin/python3 -c '
import json,sys
want=sys.argv[1]
names={m.get("name") or "" for m in json.load(sys.stdin).get("models",[])}
alts={want, want.replace(":latest","")} if want.endswith(":latest") else {want, want+":latest"}
sys.exit(0 if names & alts else 1)
' "$want"
}

victoria_health_ok() {
  curl -sf --max-time 8 "$VICTORIA_URL/health" >/dev/null
}

in_night_window() {
  local h
  h="$(date +%H)"
  h=$((10#$h))
  local start end
  start=$((10#$NIGHT_START))
  end=$((10#$NIGHT_END))
  if [ "$start" -le "$end" ]; then
    [ "$h" -ge "$start" ] && [ "$h" -lt "$end" ]
  else
    # wraps midnight: e.g. 23..6
    [ "$h" -ge "$start" ] || [ "$h" -lt "$end" ]
  fi
}

approx_free_gb() {
  /usr/bin/python3 - <<'PY'
import subprocess
try:
    out = subprocess.check_output(["memory_pressure"], text=True, stderr=subprocess.DEVNULL)
except Exception:
    print("?")
    raise SystemExit
free = None
for line in out.splitlines():
    if "Pages free" in line:
        free = int(line.split(":")[-1].strip().replace(",", ""))
        break
# Darwin page size often 16k on Apple Silicon
page = 16384
print(f"{(free or 0) * page / 1e9:.1f}" if free is not None else "?")
PY
}

unload_at() {
  local url="$1" model="$2"
  echo "==> unload $model @ $url (keep_alive=0)"
  curl -sf --max-time 180 "$url/api/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$model\",\"prompt\":\".\",\"stream\":false,\"keep_alive\":0}" >/dev/null \
    || echo "WARN: unload $model @ $url non-zero (may be cold/missing)"
}

unload_all_at() {
  local url="$1"
  local names
  names="$(curl -sf --max-time 8 "$url/api/ps" | /usr/bin/python3 -c '
import json,sys
for m in json.load(sys.stdin).get("models",[]):
    n=m.get("name") or ""
    if n: print(n)
' 2>/dev/null || true)"
  while IFS= read -r n; do
    [ -z "$n" ] && continue
    unload_at "$url" "$n"
  done <<< "$names"
}

ps_names() {
  local url="${1:-$OLLAMA}"
  curl -sf --max-time 8 "$url/api/ps" | /usr/bin/python3 -c '
import json,sys
print(",".join(sorted({(m.get("name") or "") for m in json.load(sys.stdin).get("models",[]) if m.get("name")})) or "(empty)")
' 2>/dev/null || echo "(unreachable)"
}

load_night() {
  local model="$1"
  echo "==> load $model @8192 stream:false think:false"
  curl -sf --max-time 900 "$OLLAMA/api/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$model\",\"prompt\":\"ok\",\"stream\":false,\"think\":false,\"keep_alive\":\"2h\",\"options\":{\"num_predict\":8,\"num_ctx\":8192}}" >/dev/null
  local i names
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    names="$(ps_names "$OLLAMA")"
    if echo "$names" | grep -q "$model"; then
      echo "ok: resident $model ($names)"
      return 0
    fi
    sleep 2
  done
  echo "ERROR: $model not in /api/ps after load (ps=$names)" >&2
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

cmd_pull_hint() {
  cat <<EOF
== PULL_HINT (manual — large download, do not run from day canary chat) ==
OLLAMA_HOST=127.0.0.1:11434 ollama pull $BASE_WEIGHTS
OLLAMA_HOST=127.0.0.1:11434 ollama create $NIGHT_TAG \\
  -f $ROOT/configs/models/Modelfile.victoria-night-120b

Then: bash $ROOT/scripts/brain_night_120b_window.sh PRECHECK
Night battle: bash $ROOT/scripts/brain_night_120b_window.sh NIGHT
EOF
}

cmd_precheck() {
  local fail=0
  echo "== PRECHECK night-120B =="
  echo "host_hour=$(date +%H:%M) window=${NIGHT_START}:00-${NIGHT_END}:00 FORCE_NIGHT=${FORCE_NIGHT:-0}"
  if in_night_window; then
    echo "ok: inside night window"
  else
    echo "note: outside night window (NIGHT will refuse unless FORCE_NIGHT=1)"
  fi
  local free
  free="$(approx_free_gb || echo '?')"
  echo "approx_free_gb=$free (need unload coder+MLX+hands; target free ≥20GB before load)"
  if ! curl -sf --max-time 5 "$OLLAMA/api/tags" >/dev/null; then
    echo "FAIL: 11434 unreachable ($OLLAMA)"; exit 1
  fi
  if tag_exists "$LIVE"; then
    echo "ok: live tag $LIVE"
  else
    echo "FAIL: missing live tag $LIVE"; fail=1
  fi
  if tag_exists "$BASE_WEIGHTS"; then
    echo "ok: base weights $BASE_WEIGHTS"
  else
    echo "FAIL: missing base weights $BASE_WEIGHTS — run PULL_HINT"; fail=1
  fi
  if tag_exists "$NIGHT_TAG"; then
    echo "ok: night tag $NIGHT_TAG"
  else
    echo "FAIL: missing night tag $NIGHT_TAG — run PULL_HINT create"; fail=1
  fi
  if victoria_health_ok; then
    echo "ok: victoria health"
  else
    echo "FAIL: victoria health"; fail=1
  fi
  echo "ps 11434: $(ps_names "$OLLAMA")"
  echo "ps 11436: $(ps_names "$CODER_URL")"
  echo "ps 11437: $(ps_names "$HANDS_URL")"
  if [ "$fail" -ne 0 ]; then
    echo "PRECHECK FAIL (expected until pull+create; day load forbidden)"
    exit 1
  fi
  echo "PRECHECK ok — safe to schedule NIGHT (still no auto-promote)"
}

cmd_night() {
  echo "== NIGHT 120B window =="
  if ! in_night_window && [ "${FORCE_NIGHT:-0}" != "1" ]; then
    echo "REFUSE: outside night window ${NIGHT_START}:00-${NIGHT_END}:00 (FORCE_NIGHT=1 to override)" >&2
    exit 2
  fi
  # Docker Desktop VM often reserves ~40–49GB — 120B will not fit beside it.
  # Prefer: Quit Docker before NIGHT (ollama-direct battle); reopen after ROLLBACK.
  if docker info >/dev/null 2>&1; then
    echo "WARN: Docker Desktop is UP (often ~40–49GB VM). NIGHT load may hang/OOM." >&2
    echo "WARN: Recommended: osascript -e 'quit app \"Docker\"' then re-run NIGHT; open -a Docker after ROLLBACK." >&2
    if [ "${ALLOW_NIGHT_WITH_DOCKER:-0}" != "1" ]; then
      echo "REFUSE: Docker up — set ALLOW_NIGHT_WITH_DOCKER=1 to override (not recommended)." >&2
      exit 3
    fi
  fi
  cmd_precheck
  echo "==> unload order: MLX → coder → hands → live brain"
  unload_all_at "$MLX_URL" || true
  unload_all_at "$CODER_URL" || true
  unload_all_at "$HANDS_URL" || true
  unload_at "$OLLAMA" "$LIVE" || true
  sleep 2
  echo "free after unload ≈ $(approx_free_gb) GB; ps11434=$(ps_names)"
  # Soft gate: refuse load if still clearly under target (override FORCE_LOW_FREE=1)
  free_now="$(approx_free_gb)"
  if [ "${FORCE_LOW_FREE:-0}" != "1" ] && [ "$free_now" != "?" ]; then
    awk -v f="$free_now" 'BEGIN{exit !(f+0 < 20)}' && {
      echo "REFUSE: free after unload ≈ ${free_now}GB < 20GB (FORCE_LOW_FREE=1 to override)" >&2
      exit 4
    }
  fi
  load_night "$NIGHT_TAG"
  echo "==> ollama-direct battle (baseline label for scoring file)"
  python3 "$ROOT/scripts/brain_canary_ollama_direct.py" \
    --model "$NIGHT_TAG" --model-label canary
  if [ "${FORCE_VICTORIA:-0}" = "1" ]; then
    recreate_victoria "$NIGHT_TAG"
    python3 "$ROOT/scripts/brain_canary_battle.py" --model-label canary
  else
    echo "skip victoria recreate (set FORCE_VICTORIA=1 to enable)"
  fi
  echo "NIGHT battle done. Review Δ vs day baseline 20/20; ROLLBACK before morning."
}

cmd_rollback() {
  echo "== ROLLBACK to day live =="
  unload_at "$OLLAMA" "$NIGHT_TAG" || true
  # Best-effort: reload day stack pieces if cold
  unload_all_at "$OLLAMA" || true
  load_night_day() {
    echo "==> load $LIVE @16384"
    curl -sf --max-time 600 "$OLLAMA/api/generate" \
      -H 'Content-Type: application/json' \
      -d "{\"model\":\"$LIVE\",\"prompt\":\"ok\",\"stream\":false,\"think\":false,\"keep_alive\":\"24h\",\"options\":{\"num_predict\":8,\"num_ctx\":16384}}" >/dev/null
  }
  load_night_day
  # Verify live resident
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if echo "$(ps_names)" | grep -q "$LIVE"; then
      echo "ok: resident $LIVE"
      break
    fi
    sleep 1
  done
  recreate_victoria "$LIVE"
  echo "ROLLBACK done — pinned $LIVE. Re-check 11436 coder + 11437 phi+nomic separately."
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    PRECHECK)  cmd_precheck ;;
    PULL_HINT) cmd_pull_hint ;;
    NIGHT)     cmd_night ;;
    ROLLBACK)  cmd_rollback ;;
    *) usage; exit 1 ;;
  esac
}

main "$@"
