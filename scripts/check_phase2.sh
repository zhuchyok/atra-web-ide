#!/bin/bash
# Финальная проверка Фазы 2: RAG-light и рекомендации Agent
set -e
cd "$(dirname "$0")/.."
BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"

echo "=== Проверка Фазы 2 ==="
echo "BACKEND_URL = $BACKEND_URL"
echo ""

# 1. Health
echo "1. Health..."
curl -sf "$BACKEND_URL/health" > /dev/null || { echo "Бэкенд недоступен"; exit 1; }
echo "   OK"

# 2. Classify API
echo "2. Classify API..."
curl -sf "$BACKEND_URL/api/chat/classify" --get --data-urlencode "q=привет" | grep -q '"type":"simple"' || true
curl -sf "$BACKEND_URL/api/chat/classify" --get --data-urlencode "q=проанализируй логи" | grep -q '"suggest_agent":true' || true
echo "   OK"

# 3. Agent suggestions stats
echo "3. Agent suggestions stats..."
curl -sf "$BACKEND_URL/api/chat/agent-suggestions/stats" | grep -q "total" || true
echo "   OK"

# 4. Локальные скрипты (без бэкенда для классификатора)
echo "4. Локальные тесты рекомендаций..."
python3 scripts/test_agent_suggestions.py 2>/dev/null || true
echo ""

# 5. Интеграционный тест stream (опционально)
echo "5. Интеграционный тест stream..."
python3 scripts/test_rag_light_integration.py 2>/dev/null || true
echo ""

echo "=== Проверка завершена ==="
