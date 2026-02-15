#!/usr/bin/env bash
# Запуск кураторского прогона: 2 короткие задачи, async, отчёт в docs/curator_reports/
# Использование: ./scripts/run_curator.sh   или  ./scripts/run_curator.sh --file scripts/curator_tasks.txt
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ ! -d "docs/curator_reports" ]; then
  mkdir -p docs/curator_reports
fi
# По умолчанию — две быстрые задачи; передать свои: --tasks "..." "..." или --file path
if [ $# -eq 0 ]; then
  exec python3 scripts/curator_send_tasks_to_victoria.py --tasks "привет" "что ты умеешь?" --async
fi
exec python3 scripts/curator_send_tasks_to_victoria.py "$@"
