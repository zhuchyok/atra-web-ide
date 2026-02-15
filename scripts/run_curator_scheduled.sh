#!/usr/bin/env bash
# Регулярный кураторский прогон (для cron/launchd).
# Полный список задач из scripts/curator_tasks.txt, async, отчёт в docs/curator_reports/.
# Использование (обязательно из каталога проекта или через полный путь):
#   cd /path/to/atra-web-ide && ./scripts/run_curator_scheduled.sh
#   VICTORIA_URL=http://localhost:8010 ./scripts/run_curator_scheduled.sh
# Cron (ежедневно в 9:00): 0 9 * * * cd /path/to/atra-web-ide && ./scripts/run_curator_scheduled.sh >> logs/curator.log 2>&1
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Проверка: скрипт куратора должен быть в проекте (не в ~/scripts)
if [ ! -f "$ROOT/scripts/curator_send_tasks_to_victoria.py" ]; then
  echo "Ошибка: не найден $ROOT/scripts/curator_send_tasks_to_victoria.py. Запускайте из каталога atra-web-ide: cd /path/to/atra-web-ide && ./scripts/run_curator_scheduled.sh"
  exit 1
fi
mkdir -p docs/curator_reports
TASKS_FILE="${CURATOR_TASKS_FILE:-scripts/curator_tasks.txt}"
MAX_WAIT="${CURATOR_MAX_WAIT:-600}"
export VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
CURATOR_SCRIPT="$ROOT/scripts/curator_send_tasks_to_victoria.py"
if [ ! -f "$TASKS_FILE" ]; then
  echo "Файл задач не найден: $TASKS_FILE. Используем быстрый набор (2 задачи)."
  exec python3 "$CURATOR_SCRIPT" --tasks "привет" "что ты умеешь?" --async --max-wait "$MAX_WAIT"
fi
exec python3 "$CURATOR_SCRIPT" --file "$TASKS_FILE" --async --max-wait "$MAX_WAIT"
