#!/bin/bash
# Start continuous autonomous trading system helpers

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${PROJECT_ROOT}/continuous_system.log"

cd "${PROJECT_ROOT}"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -d "venv" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

printf "🚀 Starting Continuous Trading System...\n"

python scripts/continuous_runner.py >>"${LOG_FILE}" 2>&1 &
RUNNER_PID=$!

python scripts/external_integrations.py >>"${LOG_FILE}" 2>&1 &
INTEGRATION_PID=$!

printf "📈 Continuous runner PID: %s\n" "${RUNNER_PID}" | tee -a "${LOG_FILE}"
printf "🌐 External integrations PID: %s\n" "${INTEGRATION_PID}" | tee -a "${LOG_FILE}"

printf "✅ System started successfully\n"
printf "📊 Monitor logs via: tail -f %s\n" "${LOG_FILE}"
printf "🛑 Stop with: ./stop_continuous.sh\n"

wait
