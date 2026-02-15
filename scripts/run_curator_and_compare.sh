#!/usr/bin/env bash
# Прогон куратора + сравнение с эталонами (план «как я» п.3.1).
# Использование:
#   ./scripts/run_curator_and_compare.sh              # быстрый прогон (--quick), затем сравнение по всем эталонам
#   ./scripts/run_curator_and_compare.sh --full     # полный прогон, затем то же сравнение
#   ./scripts/run_curator_and_compare.sh --write-findings   # быстрый + при падении скоринга пишем в FINDINGS_YYYY-MM-DD.md
#   ./scripts/run_curator_and_compare.sh --full --write-findings
# Таймаут среды: для быстрого ≥ 10 мин, для полного ≥ 30 мин (CURATOR_RUNBOOK §1).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
REPORTS_DIR="${ROOT}/docs/curator_reports"
STANDARDS="status_project greeting what_can_you_do list_files one_line_code"
VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"

WRITE_FINDINGS=""
FULL=""
for arg in "$@"; do
  case "$arg" in
    --write-findings) WRITE_FINDINGS="--write-findings" ;;
    --full)           FULL="1" ;;
  esac
done

if [ ! -d "$REPORTS_DIR" ]; then
  mkdir -p "$REPORTS_DIR"
fi

# 0. Ensure Victoria: если /health не отвечает — поднять контейнеры и ждать до 90 с (CURATOR_RUNBOOK §1.6)
echo "=== 0. Проверка Victoria ($VICTORIA_URL) ==="
VICTORIA_HEALTH_OK=0
if curl -sf --connect-timeout 5 "${VICTORIA_URL}/health" >/dev/null 2>&1; then
  echo "Victoria доступна."
  VICTORIA_HEALTH_OK=1
fi
if [ "$VICTORIA_HEALTH_OK" -eq 0 ] && [ -f "knowledge_os/docker-compose.yml" ]; then
  echo "Victoria не отвечает — поднимаю Knowledge OS (victoria-agent и зависимости)..."
  docker-compose -f knowledge_os/docker-compose.yml up -d 2>&1 | grep -v "level=warning" || true
  echo "Ожидание /health (до 90 с)..."
  WAITED=0
  while [ $WAITED -lt 90 ]; do
    if curl -sf --connect-timeout 5 "${VICTORIA_URL}/health" >/dev/null 2>&1; then
      echo "Victoria поднялась за ${WAITED} с."
      VICTORIA_HEALTH_OK=1
      break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
  done
fi
if [ "$VICTORIA_HEALTH_OK" -eq 0 ]; then
  echo "Ошибка: Victoria недоступна после ожидания. Запустите вручную: docker-compose -f knowledge_os/docker-compose.yml up -d" >&2
  echo "Или: bash scripts/system_auto_recovery.sh (полное восстановление стека)." >&2
  exit 1
fi
export VICTORIA_URL

echo ""
echo "=== 1. Прогон куратора ==="
if [ -n "$FULL" ]; then
  echo "Режим: полный (все задачи из curator_tasks.txt)"
  python3 scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks.txt --async --max-wait 600
else
  echo "Режим: быстрый (--quick, 2 задачи)"
  python3 scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks.txt --async --quick
fi

REPORT=$(ls -t "$REPORTS_DIR"/curator_*.json 2>/dev/null | head -1)
if [ -z "$REPORT" ] || [ ! -f "$REPORT" ]; then
  echo "Отчёт не найден в $REPORTS_DIR. Пропуск сравнения." >&2
  exit 1
fi

echo ""
echo "=== 2. Сравнение с эталонами (отчёт: $(basename "$REPORT"))${WRITE_FINDINGS:+ $WRITE_FINDINGS} ==="
for st in $STANDARDS; do
  echo "--- Эталон: $st ---"
  python3 scripts/curator_compare_to_standard.py --report "$REPORT" --standard "$st" $WRITE_FINDINGS || true
  echo ""
done
echo "Готово."
