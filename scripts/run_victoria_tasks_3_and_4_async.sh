#!/usr/bin/env bash
# Прогон задач 3 (список файлов) и 4 (что умеешь) через async_mode:
# POST /run?async_mode=true → 202 + task_id, затем опрос GET /run/status/{task_id}.
# Так избегаем обрыва долгого sync-соединения и таймаутов.
# Сохраняем полный JSON ответ в REPO_ROOT/tmp/ (или /tmp/).
# Запуск: VICTORIA_URL=${VICTORIA_URL:-http://127.0.0.1:8010} bash scripts/run_victoria_tasks_3_and_4_async.sh

set -e
VICTORIA_URL="${VICTORIA_URL:-http://127.0.0.1:8010}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${REPO_ROOT}/tmp"
mkdir -p "$OUT_DIR"
cd "$REPO_ROOT"

# Ждём стабильный health (контейнер иногда перезапускается; SERVICE_MONITOR_INITIAL_DELAY ~50 с)
echo "=== Ожидание Victoria (health) ==="
max_attempts=40
interval=3
for i in $(seq 1 "$max_attempts"); do
  if curl -s --max-time 8 "$VICTORIA_URL/health" >/dev/null 2>&1; then
    echo "   health OK (попытка $i)"
    sleep 12
    if curl -s --max-time 8 "$VICTORIA_URL/health" >/dev/null 2>&1; then
      echo "   health стабилен"
      break
    fi
  fi
  [ "$i" -eq "$max_attempts" ] && { echo "   Victoria недоступна после $max_attempts попыток (каждые ${interval}s)"; exit 1; }
  sleep "$interval"
done
echo ""

poll_until_done() {
  local task_id="$1"
  local out_file="$2"
  local label="$3"
  local max_polls="${4:-60}"
  local interval="${5:-10}"
  for ((i=1; i<=max_polls; i++)); do
    R=$(curl -s --max-time 25 "$VICTORIA_URL/run/status/$task_id" 2>/dev/null || true)
    S=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))" 2>/dev/null) || S=""
    STAGE=$(echo "$R" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stage',''))" 2>/dev/null) || STAGE=""
    # Вывод в stderr, чтобы не попадал в S4=$(...) и был виден при запуске
    echo "   $label poll $i/$max_polls: status=$S stage=$STAGE" >&2
    if [ "$S" = "completed" ] || [ "$S" = "failed" ]; then
      echo "$R" > "$out_file"
      echo "$S"
      return 0
    fi
    [ -n "$R" ] && echo "$R" > "${out_file}.last"
    [ -z "$S" ] && echo "   (пустой ответ, повтор через ${interval}s)" >&2
    sleep "$interval"
  done
  echo "timeout"
  return 1
}

# --- Задача 4: что умеешь ---
echo "=== Задача 4: что умеешь (async) ==="
R4=$(curl -s --max-time 20 -X POST "$VICTORIA_URL/run?async_mode=true" \
  -H "Content-Type: application/json" \
  -d '{"goal": "Что ты умеешь? Ответь в двух коротких предложениях.", "project_context": "atra-web-ide"}')
TID4=$(echo "$R4" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('task_id',''))" 2>/dev/null)
if [ -z "$TID4" ]; then
  echo "   ❌ Не получен task_id. Ответ: $R4"
else
  echo "   task_id: $TID4"
  # Локальные модели: один шаг LLM 30–300+ с; задача = несколько шагов. Окно 60*10=600 с (см. MODEL_TIMING_REFERENCE, measure_ollama_response_time.sh)
  S4=$(poll_until_done "$TID4" "$OUT_DIR/victoria_task4.json" "Task4" 60 10)
  if [ "$S4" = "completed" ]; then
    O4=$(python3 -c "import json; d=json.load(open('$OUT_DIR/victoria_task4.json')); print((d.get('output') or '')[:400])" 2>/dev/null || echo "—")
    echo "   ✅ Решение: $O4"
  elif [ "$S4" = "failed" ]; then
    echo "   ❌ status=failed"
    python3 -c "import json; d=json.load(open('$OUT_DIR/victoria_task4.json')); print('error:', d.get('error','')[:300])" 2>/dev/null || true
  else
    echo "   ❌ Таймаут ожидания"
  fi
fi
echo ""

# --- Задача 3: список файлов ---
echo "=== Задача 3: список файлов (async) ==="
R3=$(curl -s --max-time 20 -X POST "$VICTORIA_URL/run?async_mode=true" \
  -H "Content-Type: application/json" \
  -d '{"goal": "Выведи список файлов в корне проекта. Только имена, до 8 штук. Без пояснений.", "project_context": "atra-web-ide"}')
TID3=$(echo "$R3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('task_id',''))" 2>/dev/null)
if [ -z "$TID3" ]; then
  echo "   ❌ Не получен task_id. Ответ: $R3"
else
  echo "   task_id: $TID3"
  # Список файлов (Veronica или agent.run) — до 60*10=600 с при тяжёлой модели
  S3=$(poll_until_done "$TID3" "$OUT_DIR/victoria_task3.json" "Task3" 60 10)
  if [ "$S3" = "completed" ]; then
    O3=$(python3 -c "import json; d=json.load(open('$OUT_DIR/victoria_task3.json')); print((d.get('output') or '')[:500])" 2>/dev/null || echo "—")
    echo "   ✅ Решение: $O3"
  elif [ "$S3" = "failed" ]; then
    echo "   ❌ status=failed"
    python3 -c "import json; d=json.load(open('$OUT_DIR/victoria_task3.json')); print('error:', d.get('error','')[:300])" 2>/dev/null || true
  else
    echo "   ❌ Таймаут ожидания"
  fi
fi
echo ""

echo "=== Итог ==="
echo "   Ответы сохранены: $OUT_DIR/victoria_task4.json, $OUT_DIR/victoria_task3.json"
