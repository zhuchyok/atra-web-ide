#!/usr/bin/env bash
# Nightly Agent Gym regression check.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$ROOT_DIR/logs/agent_gym_nightly.log"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

mkdir -p "$ROOT_DIR/logs"
touch "$LOG_FILE"

echo "[$TIMESTAMP] Nightly Agent Gym run started" >> "$LOG_FILE"

cd "$ROOT_DIR"
if [ -x "./.venv/bin/python" ]; then
  PYTHON="./.venv/bin/python"
elif [ -x "./.venv-openssl/bin/python" ]; then
  PYTHON="./.venv-openssl/bin/python"
else
  PYTHON="python3"
fi

run() {
  local label="$1"
  shift
  if "$@" >>"$LOG_FILE" 2>&1; then
    echo "[$TIMESTAMP] ✅ $label" >>"$LOG_FILE"
  else
    local code=$?
    echo "[$TIMESTAMP] ❌ $label (exit $code)" >>"$LOG_FILE"
    return $code
  fi
}

run "agent_gym_nightly" "$PYTHON" scripts/run_agent_gym_nightly.py \
  --scenarios agent_gym/configs/sample_scenarios.json \
  --db trading.db \
  --output agent_gym/reports/latest.json \
  --baseline agent_gym/reports/baseline.json \
  --diff-output agent_gym/reports/nightly_diff.json \
  --metrics-output metrics/agent_gym_regressions.prom \
  --print-summary

echo "[$TIMESTAMP] Nightly Agent Gym run finished" >> "$LOG_FILE"


