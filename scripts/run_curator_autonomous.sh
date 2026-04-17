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
# Подхват переменных из .env при запуске по cron/launchd
# Сохраняем VICTORIA_URL и DATABASE_URL до source .env (wrapper/caller мог задать localhost)
_pre_victoria_url="$VICTORIA_URL"
_pre_database_url="$DATABASE_URL"
_pre_redis_url="$REDIS_URL"
if [ -f "$ROOT/.env" ]; then set -a; source "$ROOT/.env"; set +a; fi
# Восстанавливаем переменные если они были заданы явно из вызывающей среды (wrapper/launchd)
# — это важно: .env содержит victoria-agent:8000 и knowledge_pgbouncer:6432 (Docker-сеть),
#   но куратор запускается на хосте и использует localhost:8010, localhost:5432, localhost:6381
if [ -n "$_pre_victoria_url" ]; then
  VICTORIA_URL="$_pre_victoria_url"
fi
if [ -n "$_pre_database_url" ]; then
  DATABASE_URL="$_pre_database_url"
fi
if [ -n "$_pre_redis_url" ]; then
  REDIS_URL="$_pre_redis_url"
fi
REPORTS_DIR="${ROOT}/docs/curator_reports"
STANDARDS="status_project greeting what_can_you_do list_files one_line_code code_audit"
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
  python3 scripts/curator_send_tasks_to_victoria.py --file scripts/curator_tasks.txt --async --max-wait 3600
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
  # greeting и status_project: достаточно 1 совпадения из списка (порог 0.2)
  THRESHOLD="0.5"
  if [ "$st" = "greeting" ] || [ "$st" = "status_project" ]; then
    THRESHOLD="0.2"
  fi
  $PYTHON_CMD scripts/curator_compare_to_standard.py --report "$REPORT" --standard "$st" \
    --threshold "$THRESHOLD" --write-findings --create-task-on-divergence || true
  echo ""
done

if [ -n "$SYNC_RAG" ] && [ -n "$DATABASE_URL" ]; then
  echo "=== 3. Синхронизация эталонов в RAG ==="
  $PYTHON_CMD scripts/curator_add_standard_to_knowledge.py || true
  echo ""
fi

echo "Готово. При расхождениях: FINDINGS в docs/curator_reports/; задачи в БД (если задан DATABASE_URL)."

# [SINGULARITY 21.5] Шаг 4: Victoria само-анализ + авто-патч через FAST_PATCH_PATH
echo "=== 4. Victoria Self-Curator: само-анализ + авто-патч ==="
$PYTHON_CMD scripts/victoria_self_curator.py --skip-curator || true
echo ""

# [SINGULARITY 21.25] Шаг 5: Замкнутый цикл — Victoria сама генерирует следующие задачи
echo "=== 5. Victoria Task Generator: расширение очереди аудита ==="
$PYTHON_CMD scripts/victoria_task_generator.py || true
echo "Задачи в очереди: $(wc -l < scripts/curator_tasks.txt | tr -d ' ')"
echo ""

# [SINGULARITY 21.25] Шаг 6: Сохранение FINDINGS в knowledge_nodes
echo "=== 6. Findings → Knowledge Nodes ==="
$PYTHON_CMD scripts/curator_findings_to_knowledge.py || true
echo ""

# [SINGULARITY 21.27] Шаг 6b: Обновить ключевые доки в RAG (только если есть DATABASE_URL)
echo "=== 6b. Docs → RAG (ключевые доки проекта) ==="
if [ -n "$DATABASE_URL" ]; then
  $PYTHON_CMD scripts/ingest_docs_to_rag.py || true
else
  echo "DATABASE_URL не задан — пропускаем обновление RAG"
fi
echo ""

# [SINGULARITY 21.25] Шаг 7: Ежедневный дайджест в ntfy
echo "=== 7. Daily Summary Report → ntfy ==="
$PYTHON_CMD scripts/daily_summary_report.py || true
echo ""

echo "=== ЦИКЛ ЗАВЕРШЁН ==="
echo "Следующий прогон получит расширенный список задач."
