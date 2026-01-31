#!/bin/bash

# Полный цикл risk-мониторинга: обновление флагов, логирование и отправка в Telegram.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$ROOT_DIR/.venv/bin/activate"
LOG_DIR="$ROOT_DIR/logs"

RUN_MONITOR="$ROOT_DIR/scripts/run_risk_monitor.py"
RISK_REPORT="$ROOT_DIR/scripts/report_risk_status.py"
SEND_REPORT="$ROOT_DIR/scripts/send_risk_status_report.py"
INFRA_REPORT="$ROOT_DIR/scripts/report_infra_status.py"

if [[ -f "$VENV_PATH" ]]; then
  # shellcheck disable=SC1090
  source "$VENV_PATH"
fi

mkdir -p "$LOG_DIR"

python3 "$RUN_MONITOR" >> "$LOG_DIR/risk_monitor.log" 2>&1
python3 "$RISK_REPORT" --format text >> "$LOG_DIR/risk_status.log" 2>&1
python3 "$INFRA_REPORT" --format text >> "$LOG_DIR/infra_status.log" 2>&1
python3 "$SEND_REPORT" \
  --include-infra \
  --backups-dir "$ROOT_DIR/backups" \
  --bot-pid "$ROOT_DIR/bot.pid" \
  --bot-log "$ROOT_DIR/bot.log" \
  --lock-file "$ROOT_DIR/atra.lock" \
  >> "$LOG_DIR/risk_status_send.log" 2>&1

