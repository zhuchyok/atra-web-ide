#!/bin/bash

# Ежедневный запуск сводного отчёта качества сигналов и сайзинга.
# Использование:
#   ./scripts/run_daily_quality_report.sh
# (скрипт можно повесить на cron/systemd-timer)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$ROOT_DIR/.venv/bin/activate"
REPORT_SCRIPT="$ROOT_DIR/scripts/daily_quality_report.py"
PERF_SCRIPT="$ROOT_DIR/scripts/export_performance_metrics.py"
OUTPUT_DIR="$ROOT_DIR/data/reports"
PERF_REPORT="$OUTPUT_DIR/performance_live_vs_backfill.json"

if [[ ! -f "$REPORT_SCRIPT" ]]; then
  echo "❌ Не найден скрипт $REPORT_SCRIPT"
  exit 1
fi

if [[ ! -f "$PERF_SCRIPT" ]]; then
  echo "❌ Не найден скрипт $PERF_SCRIPT"
  exit 1
fi

if [[ -f "$VENV_PATH" ]]; then
  # shellcheck disable=SC1090
  source "$VENV_PATH"
fi

mkdir -p "$OUTPUT_DIR"

python3 "$REPORT_SCRIPT" --hours 24 --output-dir "$OUTPUT_DIR"

python3 "$PERF_SCRIPT" \
  --trade-modes all live backfill futures \
  --output "$PERF_REPORT"

# Рассылаем отчёт в Telegram администратору (ID берётся из user_data.json)
python3 "$ROOT_DIR/scripts/send_daily_quality_report.py"

