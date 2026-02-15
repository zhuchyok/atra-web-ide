#!/usr/bin/env bash
# Замер времени одного ответа модели (Ollama и при наличии MLX).
# Помогает понять, почему async-задачи Victoria долго в статусе running: каждая ступень (understand_goal, plan, шаги) — вызов LLM; локальные модели отвечают 10–300+ с в зависимости от размера.
# Запуск: OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://localhost:11434} bash scripts/measure_ollama_response_time.sh

set -e
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
MLX_URL="${MLX_BASE_URL:-http://localhost:11435}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Простой промпт (как один шаг Victoria)
PROMPT='Ответь одним словом: сколько будет 2+2?'
# Модель: первая доступная или из env
MODEL="${VICTORIA_MODEL:-}"

echo "=== Замер времени ответа модели (один запрос) ==="
echo "   OLLAMA_URL=$OLLAMA_URL"
echo "   MLX_URL=$MLX_URL"
echo "   Промпт: $PROMPT"
echo ""

# Узнаём первую модель Ollama с generate (полное имя с тегом, пропускаем embedding-only)
if [ -z "$MODEL" ]; then
  MODEL=$(curl -s --max-time 5 "$OLLAMA_URL/api/tags" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    models = d.get('models') or []
    skip = {'nomic-embed-text', 'nomic-embed', 'mxbai-embed', 'all-minilm'}
    for m in models:
        full = (m.get('name') or '').strip()
        if not full:
            continue
        base = full.split(':')[0].lower()
        if base in skip:
            continue
        print(full)
        break
    else:
        print('phi3.5:3.8b')
except Exception:
    print('phi3.5:3.8b')
" 2>/dev/null)
  MODEL="${MODEL:-phi3.5:3.8b}"
fi
echo "   Модель Ollama: $MODEL"
echo ""

# Ollama: /api/generate (один запрос, замер до первого токена и до конца)
echo "--- Ollama: один запрос /api/generate ---"
START=$(python3 -c "import time; print(time.time())")
HTTP_CODE=$(curl -s -o /tmp/ollama_measure_out.json -w "%{http_code}" --max-time 600 -X POST "$OLLAMA_URL/api/generate" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODEL\", \"prompt\": \"$PROMPT\", \"stream\": false}")
END=$(python3 -c "import time; print(time.time())")
OLLAMA_ELAPSED=$(python3 -c "print(round($END - $START, 2))")
echo "   HTTP $HTTP_CODE, время: ${OLLAMA_ELAPSED} с"
if [ "$HTTP_CODE" = "200" ]; then
  echo "   Ответ (начало): $(python3 -c "import json; d=json.load(open('/tmp/ollama_measure_out.json')); print((d.get('response') or '')[:150])" 2>/dev/null || echo "—")"
else
  echo "   Тело: $(head -c 200 /tmp/ollama_measure_out.json 2>/dev/null)"
fi
echo ""

# MLX: если доступен, аналогичный замер (эндпоинт может отличаться)
if curl -s --max-time 3 "$MLX_URL/health" >/dev/null 2>&1; then
  echo "--- MLX API: один запрос ---"
  START=$(python3 -c "import time; print(time.time())")
  # Типичный эндпоинт MLX: /v1/chat/completions или /generate
  MLX_CODE=$(curl -s -o /tmp/mlx_measure_out.json -w "%{http_code}" --max-time 600 -X POST "$MLX_URL/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"mlx-community/Phi-3-mini-4k-instruct-4bit\", \"messages\": [{\"role\": \"user\", \"content\": \"$PROMPT\"}], \"max_tokens\": 50}" 2>/dev/null)
  END=$(python3 -c "import time; print(time.time())")
  ELAPSED=$(python3 -c "print(round($END - $START, 2))")
  echo "   HTTP $MLX_CODE, время: ${ELAPSED} с"
else
  echo "--- MLX: не доступен (пропуск) ---"
fi
echo ""

echo "=== Итог ==="
echo "   Один вызов LLM (Ollama): ${OLLAMA_ELAPSED:-?} с. В Victoria одна задача = несколько вызовов (understand, plan, шаги); для тяжёлых моделей окно опроса async увеличивайте (см. run_victoria_tasks_3_and_4_async.sh: 60 опросов по 10 с)."
