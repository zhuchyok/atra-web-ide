#!/bin/bash
# Стресс-тест ATRA Web IDE (День 6–7, Фаза 3)
# Требует: pip install locust; backend на http://localhost:8080

set -e

HOST="${HOST:-http://localhost:8080}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-10}"
RUN_TIME="${RUN_TIME:-2m}"
OUT_DIR="${OUT_DIR:-./scripts/load_test/out}"

echo "🚀 Стресс-тест системы"
echo "   Host: $HOST"
echo "   Users: $USERS"
echo "   Spawn rate: $SPAWN_RATE"
echo "   Run time: $RUN_TIME"
echo ""

# 1. Проверка сервисов (таймаут 5 сек — не зависать, если backend не отвечает)
echo "1. Проверка backend..."
curl -sf --connect-timeout 5 --max-time 10 "$HOST/health" > /dev/null || {
  echo "❌ Backend не запущен на $HOST."
  echo "   Сначала: docker-compose -f knowledge_os/docker-compose.yml up -d"
  echo "   Затем:   docker-compose up -d"
  exit 1
}
echo "   OK"
echo ""

# 2. Очистка кэшей (опционально, таймаут 5 сек)
echo "2. Очистка кэшей..."
curl -s --connect-timeout 5 --max-time 10 -X POST "$HOST/api/plan-cache/clear" > /dev/null || true
curl -s --connect-timeout 5 --max-time 10 -X POST "$HOST/api/rag-optimization/cache/clear" > /dev/null || true
echo "   OK"
echo ""

# 3. Запуск Locust (headless)
mkdir -p "$OUT_DIR"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
LOADTEST_VENV="$REPO_ROOT/scripts/load_test/.venv"
LOCUST_CMD=""
if [ -f "$LOADTEST_VENV/bin/activate" ] && "$LOADTEST_VENV/bin/python" -c "import locust" 2>/dev/null; then
  LOCUST_CMD="$LOADTEST_VENV/bin/python -m locust"
elif command -v locust >/dev/null 2>&1; then
  LOCUST_CMD="locust"
elif python3 -c "import locust" 2>/dev/null; then
  LOCUST_CMD="python3 -m locust"
else
  echo "⚠️  Locust не найден (на macOS не используйте системный pip)."
  echo "   Вариант 1 — venv для тестов: ./scripts/load_test/setup_venv.sh"
  echo "   Вариант 2 — pipx: brew install pipx && pipx install locust"
  exit 1
fi
echo "3. Запуск Locust (headless)..."
$LOCUST_CMD -f scripts/load_test/locustfile.py \
  --host="$HOST" \
  --users="$USERS" \
  --spawn-rate="$SPAWN_RATE" \
  --run-time="$RUN_TIME" \
  --headless \
  --csv="$OUT_DIR/load_test" \
  --html="$OUT_DIR/load_test_report.html" || true
# Locust выходит с кодом 1, если были неудачные запросы (503, 500) — это нормально для стресс-теста

# 4. Краткий отчёт
echo ""
echo "4. Результаты:"
if [ -f "$OUT_DIR/load_test_stats.csv" ]; then
  echo "   Файлы: $OUT_DIR/load_test_*.csv, $OUT_DIR/load_test_report.html"
  # Последняя строка = Aggregated; колонки: Type,Name,Request Count,Failure Count,...,Requests/s (10),... Average Response Time (6)
  tail -n 1 "$OUT_DIR/load_test_stats.csv" | awk -F',' '{
    print "   Запросов: " $3
    print "   Ошибок: " $4
    print "   RPS (сред): " $10
    print "   Время ответа (сред, мс): " $6
  }'
else
  echo "   (CSV не создан — проверьте вывод locust)"
fi

# 5. Метрики после теста
echo ""
echo "5. Метрики backend (выборка):"
curl -s "$HOST/metrics" 2>/dev/null | grep -E "^(chat_requests_total|rag_requests_total|errors_total)" | head -5 || echo "   (эндпоинт /metrics недоступен)"

# 6. Latency RAG (если бенчмарк запускался ранее)
echo ""
echo "6. Latency RAG (P95 цель < 300ms):"
LATENCY_JSON=$(curl -s "$HOST/api/latency/benchmark" 2>/dev/null || echo "{}")
if echo "$LATENCY_JSON" | grep -q '"p95_ms"'; then
  P95=$(echo "$LATENCY_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('p95_ms','?'))" 2>/dev/null || echo "?")
  echo "   P95: ${P95} ms (из последнего бенчмарка)"
  echo "   Запуск бенчмарка: python scripts/benchmark_latency.py"
else
  echo "   Нет данных. Запустите: python scripts/benchmark_latency.py"
fi

echo ""
echo "✅ Стресс-тест завершён"
