#!/bin/bash
# Проверка оптимизаций RAG-light (Фаза 3, день 3–4)
set -e
cd "$(dirname "$0")/.."
BACKEND_URL="${BACKEND_URL:-http://localhost:8080}"

echo "=== Проверка оптимизаций RAG-light (День 3–4) ==="
echo "BACKEND_URL = $BACKEND_URL"
echo ""

echo "1. Health..."
curl -sf "$BACKEND_URL/health" > /dev/null || { echo "Бэкенд недоступен"; exit 1; }
echo "   OK"

echo "2. RAG optimization stats..."
curl -s "$BACKEND_URL/api/rag-optimization/stats" | head -20
echo ""

echo "3. Plan cache stats..."
curl -s "$BACKEND_URL/api/plan-cache/stats"
echo ""

echo "=== Проверка завершена ==="
