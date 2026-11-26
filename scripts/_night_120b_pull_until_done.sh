#!/bin/bash
# Durable pull→create for Wave 0. NIGHT only if AUTO_NIGHT=1.
# Progress: trust Ollama completed/total (partial file may be preallocated).
set -u
ROOT="/Users/bikos/Documents/atra-web-ide"
LOG="$ROOT/logs/night_120b_pull.log"
PIPE="$ROOT/logs/night_120b_pipeline.log"
PIDF="$ROOT/logs/night_120b_pipeline.pid"
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_HOST
echo "$$" > "$PIDF"
log(){ echo "$(date -Iseconds) $*" | tee -a "$PIPE"; }

log START_PIPELINE
while true; do
    if ollama list 2>/dev/null | grep -q 'gpt-oss:120b'; then
    log PULL_DONE
    if ! ollama list 2>/dev/null | grep -q 'victoria-night:120b'; then
      log CREATE_NIGHT
      ollama create victoria-night:120b \
        -f "$ROOT/configs/models/Modelfile.victoria-night-120b" >>"$PIPE" 2>&1 \
        || log CREATE_FAIL
    else
      log NIGHT_TAG_EXISTS
    fi
    # Post-pull: PRECHECK → recommend NIGHT (never auto) → ROLLBACK reminder
    WIN="$ROOT/scripts/brain_night_120b_window.sh"
    if bash "$WIN" PRECHECK >>"$PIPE" 2>&1; then
      log PRECHECK_OK
      touch "$ROOT/logs/night_120b_READY"
      FREE=$(/usr/bin/python3 - <<'PY' 2>/dev/null || echo '?'
import subprocess
try:
    out = subprocess.check_output(["memory_pressure"], text=True, stderr=subprocess.DEVNULL)
except Exception:
    print("?"); raise SystemExit
free = next((int(l.split(":")[-1].strip().replace(",","")) for l in out.splitlines() if "Pages free" in l), None)
print(f"{(free or 0)*16384/1e9:.1f}" if free is not None else "?")
PY
)
      log "approx_free_gb=${FREE} (NIGHT unloads MLX→coder→hands→live first; gate free≥20GB before load)"
      log "RECOMMEND: bash $WIN NIGHT # night window or FORCE_NIGHT=1; AUTO_NIGHT=1 to opt-in here"
      log "MORNING_ROLLBACK: bash $WIN ROLLBACK # unload night, pin victoria-qwen38:latest"
    else
      log PRECHECK_FAIL_see_pipeline_log
    fi
    if [ "${AUTO_NIGHT:-0}" = "1" ]; then
      log RUN_NIGHT_opt_in
      bash "$WIN" NIGHT >>"$PIPE" 2>&1 || log NIGHT_FAIL
      log "REMINDER_ROLLBACK: bash $WIN ROLLBACK before morning"
    else
      log SKIP_NIGHT_set_AUTO_NIGHT=1_to_run
    fi
    log PIPELINE_EXIT
    exit 0
  fi
  if ! pgrep -f 'ollama pull gpt-oss:120b' >/dev/null 2>&1; then
    log RESTART_PULL
    # Prefer streaming CLI so resume continues; log UI % is completed/total (~17/65GiB now)
    nohup ollama pull gpt-oss:120b >>"$LOG" 2>&1 &
    echo $! > "$ROOT/logs/night_120b_pull.pid"
  fi
  # Heartbeat from CLI log only (do NOT call /api/pull — starts a second pull).
  HB=$(/usr/bin/python3 - <<'PY' 2>/dev/null
from pathlib import Path
p = Path("/Users/bikos/Documents/atra-web-ide/logs/night_120b_pull.log")
if not p.exists():
    print("no_log"); raise SystemExit
raw = p.read_bytes()[-4000:].decode("utf-8", "replace").replace("\r", "\n")
lines = [ln for ln in raw.split("\n") if "pulling a5b03e" in ln and "%" in ln]
print(lines[-1][:100] if lines else "waiting")
PY
)
  log "HB $HB"
  sleep 90
done
