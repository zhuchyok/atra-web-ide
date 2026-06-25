#!/usr/bin/env bash
# Проверка цепочки Open WebUI → Backend → Victoria (ask_victoria).
# Запуск: ./scripts/test_ask_victoria_chain.sh
# Переменные: BACKEND_URL (default http://localhost:8080), ASK_TIMEOUT (default 120)

set -e
BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"
ASK_TIMEOUT="${ASK_TIMEOUT:-120}"

echo "=== 1. Backend health (Victoria dependency) ==="
health=$(curl -s -m 10 "${BACKEND_URL}/health" || true)
if [ -z "$health" ]; then
  echo "FAIL: Backend не ответил на /health. Проверьте BACKEND_URL=$BACKEND_URL и что backend запущен."
  exit 1
fi
echo "$health" | head -5
victoria_status=$(echo "$health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('dependencies',{}).get('victoria','?'))" 2>/dev/null || echo "?")
echo "Victoria в /health: $victoria_status"
echo ""

echo "=== 2. POST /api/chat/ask-victoria (goal: Скажи одно слово: ок) timeout=${ASK_TIMEOUT}s ==="
resp=$(curl -s -X POST "${BACKEND_URL}/api/chat/ask-victoria" \
  -H "Content-Type: application/json" \
  -d '{"goal":"Скажи одно слово: ок","project_context":"atra-web-ide"}' \
  --max-time "$ASK_TIMEOUT" -w $'\n%{http_code}' 2>/dev/null || echo $'\n000')
code="${resp##*$'\n'}"
body="${resp%$'\n'*}"
body="$(printf '%s' "$body" | python3 -c "import sys; print(sys.stdin.read()[:600], end='')")"
echo "HTTP $code"
echo "Body (first 600 chars):"
echo "$body"
echo ""

if [ "$code" = "200" ]; then
  echo "OK: ask_victoria вернул 200. Цепочка Backend → Victoria работает."
elif [ "$code" = "503" ]; then
  echo "FAIL: 503 — см. сообщение выше (таймаут / нет связи / перегрузка). Проверьте логи backend и что Victoria запущена (порт 8010 или victoria-agent)."
  exit 2
elif [ "$code" = "000" ]; then
  echo "FAIL: Таймаут или нет соединения с backend."
  exit 3
else
  echo "FAIL: неожиданный код $code."
  exit 4
fi
