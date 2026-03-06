#!/usr/bin/env bash
# Автономный куратор «под ключ»: прогон Victoria → сравнение с эталонами → при расхождении запись в FINDINGS и создание задачи в БД.
# Без Cursor: только VICTORIA_URL и DATABASE_URL (локальные или внутренние).
#
# Использование:
#   ./scripts/run_curator_autonomous.sh              # быстрый прогон (2 задачи), сравнение, при расхождении — FINDINGS + задачи в БД
#   ./scripts/run_curator_autonomous.sh --full        # полный прогон, затем то же
#   ./scripts/run_curator_autonomous.sh --sync-rag    # в конце синхронизировать эталоны в RAG (curator_add_standard_to_knowledge)
#   DATABASE_URL=postgresql://... ./scripts/run_curator_autonomous.sh
#
# Требования: Victoria доступна (VICTORIA_URL); для создания задач в БД — DATABASE_URL. Таймаут среды: быстрый ≥ 10 мин, полный ≥ 30 мин.
# См. CURATOR_RUNBOOK §6 «Путь к автономности».
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Подхват DATABASE_URL и др. из .env при запуске по cron/launchd
if [ -f "$ROOT/.env" ]; then set -a; source "$ROOT/.env"; set +a; fi
REPORTS_DIR="${ROOT}/docs/curator_reports"
STANDARDS="status_project greeting what_can_you_do list_files one_line_code"
VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
# DATABASE_URL для --create-task-on-divergence (если не задан — задачи не создаются, только FINDINGS)
export DATABASE_URL="${DATABASE_URL:-}"

FULL=""
SYNC_RAG=""
for arg in "$@"; do
  case "$arg" in
    --full)     FULL="1" ;;
    --sync-rag) SYNC_RAG="1" ;;
  esac
done

if [ ! -d "$REPORTS_DIR" ]; then
  mkdir -p "$REPORTS_DIR"
fi

# 0. Проверка Victoria (как в run_curator_and_compare.sh)
echo "=== 0. Проверка Victoria ($VICTORIA_URL) ==="
VICTORIA_HEALTH_OK=0
if curl -sf --connect-timeout 5 "${VICTORIA_URL}/health" >/dev/null 2>&1; then
  echo "Victoria доступна."
  VICTORIA_HEALTH_OK=1
fi
if [ "$VICTORIA_HEALTH_OK" -eq 0 ] && [ -f "knowledge_os/docker-compose.yml" ]; then
  echo "Victoria не отвечает — поднимаю Knowledge OS..."
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
  echo "Ошибка: Victoria недоступна. Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d" >&2
  exit 1
fi
export VICTORIA_URL

echo ""
echo "=== 1. Прогон куратора ==="
if [ -n "$FULL" ]; then
  echo "Режим: полный"
  python3 scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks.txt --async --max-wait 600
else
  echo "Режим: быстрый (2 задачи)"
  python3 scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks.txt --async --quick
fi

REPORT=$(ls -t "$REPORTS_DIR"/curator_*.json 2>/dev/null | head -1)
if [ -z "$REPORT" ] || [ ! -f "$REPORT" ]; then
  echo "Отчёт не найден. Пропуск сравнения." >&2
  exit 1
fi

echo ""
echo "=== 2. Сравнение с эталонами + FINDINGS + создание задач при расхождении ==="
# Используем Python из knowledge_os/.venv при наличии — там есть asyncpg для создания задач в БД
PYTHON_CMD="python3"
if [ -x "$ROOT/knowledge_os/.venv/bin/python" ]; then
  PYTHON_CMD="$ROOT/knowledge_os/.venv/bin/python"
fi
for st in $STANDARDS; do
  echo "--- Эталон: $st ---"
  $PYTHON_CMD scripts/curator_compare_to_standard.py --report "$REPORT" --standard "$st" \
    --write-findings --create-task-on-divergence || true
  echo ""
done

if [ -n "$SYNC_RAG" ] && [ -n "$DATABASE_URL" ]; then
  echo "=== 3. Синхронизация эталонов в RAG ==="
  $PYTHON_CMD scripts/curator_add_standard_to_knowledge.py || true
  echo ""
fi

echo "Готово. При расхождениях: FINDINGS в docs/curator_reports/; задачи в БД (если задан DATABASE_URL)."
