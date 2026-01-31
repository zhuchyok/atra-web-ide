#!/usr/bin/env bash
# Проверка: в SSE-стриме чата должны быть события step до chunk.
# Запуск после перезапуска бэкенда: docker-compose restart backend или uvicorn.

set -e
API="${1:-http://localhost:8080}"
echo "Проверка $API/api/chat/stream (первые 3 сек)..."
OUT=$(curl -s -N -m 5 -X POST "$API/api/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"content":"тест шагов","expert_name":"Виктория","use_victoria":true,"mode":"agent"}' 2>/dev/null | head -c 3000)
if echo "$OUT" | grep -q '"type": "step"'; then
  echo "OK: в ответе есть step-события."
  echo "$OUT" | grep '"type":' | head -10
else
  echo "Нет step в ответе. Перезапустите бэкенд (docker-compose restart backend или uvicorn) и повторите."
  echo "Первые строки ответа:"
  echo "$OUT" | head -20
  exit 1
fi
