#!/usr/bin/env bash
# Nightly Bitget stop-loss validation suite.
#
# Запускает:
#  1) run_risk_monitor.py --check-bitget-stoploss
#  2) pytest tests/unit/test_exchange_adapter_bitget.py
#  3) scripts/test_bitget_stop_orders.py (при наличии ключей)
# Результат пишет в logs/test_results.log

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$ROOT_DIR/logs/test_results.log"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

mkdir -p "$ROOT_DIR/logs"
touch "$LOG_FILE"

echo "[$TIMESTAMP] Nightly Bitget checks started" >> "$LOG_FILE"

run() {
  local label="$1"
  shift
  if "$@"; then
    echo "[$TIMESTAMP] ✅ $label" >> "$LOG_FILE"
  else
    local code=$?
    echo "[$TIMESTAMP] ❌ $label (exit $code)" >> "$LOG_FILE"
    return $code
  fi
}

cd "$ROOT_DIR"
if [ -x "./.venv/bin/python" ]; then
  PYTHON="./.venv/bin/python"
elif [ -x "./.venv-openssl/bin/python" ]; then
  PYTHON="./.venv-openssl/bin/python"
else
  PYTHON="python3"
fi
PYTEST=("$PYTHON" "-m" "pytest")

run "run_risk_monitor check" "$PYTHON" scripts/run_risk_monitor.py --check-bitget-stoploss
if "${PYTEST[@]}" --version >/dev/null 2>&1; then
  run "pytest exchange_adapter_bitget" "${PYTEST[@]}" tests/unit/test_exchange_adapter_bitget.py
else
  echo "[$TIMESTAMP] ⚠️ pytest отсутствует (пропускаю unit-тесты)" >> "$LOG_FILE"
fi
BITGET_ENV_PRESENT=0
if grep -q "^BITGET_API_KEY" "$ROOT_DIR/env" 2>/dev/null; then
  BITGET_ENV_PRESENT=1
fi
if [ -n "${BITGET_API_KEY:-}" ]; then
  BITGET_ENV_PRESENT=1
fi

if [ "$BITGET_ENV_PRESENT" -eq 1 ]; then
  run "test_bitget_stop_orders" "$PYTHON" scripts/test_bitget_stop_orders.py || true
else
  echo "[$TIMESTAMP] ⚠️ test_bitget_stop_orders skipped (нет Bitget ключей)" >> "$LOG_FILE"
fi

echo "[$TIMESTAMP] Nightly Bitget checks finished" >> "$LOG_FILE"

