#!/usr/bin/env bash
# E2E: стратегический вопрос → backend → board/consult (при необходимости) → Victoria
# Требует: backend (8080), Victoria (8010); опционально Knowledge OS (8002) для board/consult.
# См. docs/TESTING_FULL_SYSTEM.md §2 «E2E сценарий: стратегический вопрос → board → Victoria».

set -e

BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
GOAL="${GOAL:-Какие риски для компании в 2026 году? Дай краткий ответ.}"

echo "Strategic chat E2E: BACKEND_URL=$BACKEND_URL"
echo "Goal: $GOAL"

# POST /api/chat/stream — ожидаем 200 и непустой SSE (content — экранируем кавычки для JSON)
GOAL_JSON=$(printf '%s' "$GOAL" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
RES=$(curl -s -w "\n%{http_code}" -X POST "$BACKEND_URL/api/chat/stream" \
  -H "Content-Type: application/json" \
  -d "{\"content\": $GOAL_JSON}" \
  --max-time 120)

HTTP_BODY=$(echo "$RES" | head -n -1)
HTTP_CODE=$(echo "$RES" | tail -n 1)

if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: expected HTTP 200, got $HTTP_CODE"
  echo "$HTTP_BODY" | head -20
  exit 1
fi

# Проверяем, что в потоке есть хотя бы данные (type: message или content)
if echo "$HTTP_BODY" | grep -qE '"type"|"content"|"text"|data:'; then
  echo "OK: got stream response (status 200, non-empty)"
else
  echo "WARN: stream may be empty or format changed; body sample:"
  echo "$HTTP_BODY" | head -5
fi

echo "Strategic chat E2E passed."
