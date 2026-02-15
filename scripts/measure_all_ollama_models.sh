#!/usr/bin/env bash
# Замер времени ответа **каждой** модели Ollama (один запрос на модель).
# Результат: таблица модель → секунды; сохраняется в tmp/ollama_model_timings.txt и .json.
# Для тестирования и настройки таймаутов (OLLAMA_EXECUTOR_TIMEOUT, SERVICE_MONITOR_INITIAL_DELAY).
# Запуск: OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://localhost:11434} bash scripts/measure_all_ollama_models.sh

set -e
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${REPO_ROOT}/tmp"
mkdir -p "$OUT_DIR"
cd "$REPO_ROOT"

# Таймаут на один запрос к модели (если не ответила — пропускаем)
REQUEST_TIMEOUT="${OLLAMA_MEASURE_TIMEOUT:-120}"
PROMPT='Ответь одним словом: сколько будет 2+2?'

# Список моделей (пропускаем embedding-only)
MODELS_JSON=$(curl -s --max-time 10 "$OLLAMA_URL/api/tags" 2>/dev/null || echo '{"models":[]}')
MODELS=$(echo "$MODELS_JSON" | python3 -c "
import sys, json
skip = {'nomic-embed-text', 'nomic-embed', 'mxbai-embed', 'all-minilm'}
try:
    d = json.load(sys.stdin)
    for m in d.get('models') or []:
        full = (m.get('name') or '').strip()
        if not full:
            continue
        base = full.split(':')[0].lower()
        if base in skip:
            continue
        print(full)
except Exception:
    pass
" 2>/dev/null)

if [ -z "$MODELS" ]; then
  echo "Нет доступных моделей Ollama по $OLLAMA_URL (или только embedding)."
  exit 0
fi

echo "=== Замер времени ответа каждой модели Ollama ==="
echo "   URL: $OLLAMA_URL"
echo "   Промпт: $PROMPT"
echo "   Таймаут на запрос: ${REQUEST_TIMEOUT} с"
echo ""

# Таблица: модель | время (с) | статус
TABLE="$OUT_DIR/ollama_model_timings.txt"
JSON="$OUT_DIR/ollama_model_timings.json"
echo "model	time_sec	status" > "$TABLE"
echo "[" > "$JSON"
first=true

while IFS= read -r model; do
  [ -z "$model" ] && continue
  START=$(python3 -c "import time; print(time.time())")
  HTTP_CODE=$(curl -s -o /tmp/ollama_one_out.json -w "%{http_code}" --max-time "$REQUEST_TIMEOUT" -X POST "$OLLAMA_URL/api/generate" \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"$model\", \"prompt\": \"$PROMPT\", \"stream\": false}" 2>/dev/null) || HTTP_CODE="000"
  END=$(python3 -c "import time; print(time.time())")
  ELAPSED=$(python3 -c "print(round($END - $START, 2))")

  if [ "$HTTP_CODE" = "200" ]; then
    STATUS="ok"
    echo "   $model: ${ELAPSED} с"
  else
    STATUS="http_${HTTP_CODE}"
    echo "   $model: ${ELAPSED} с (HTTP $HTTP_CODE)"
  fi

  echo "$model	$ELAPSED	$STATUS" >> "$TABLE"

  [ "$first" = false ] && echo "," >> "$JSON"
  first=false
  echo "  {\"model\": \"$model\", \"time_sec\": $ELAPSED, \"status\": \"$STATUS\"}" >> "$JSON"

done <<< "$MODELS"

echo "" >> "$JSON"
echo "]" >> "$JSON"
echo ""
echo "=== Результат ==="
echo "   Таблица: $TABLE"
column -t -s $'\t' "$TABLE" 2>/dev/null || cat "$TABLE"
echo ""
echo "   JSON: $JSON"
echo "   Используйте для настройки OLLAMA_EXECUTOR_TIMEOUT и тестов (см. MODEL_TIMING_REFERENCE.md)."
