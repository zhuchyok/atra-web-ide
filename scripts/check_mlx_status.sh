#!/bin/bash
# Скрипт для просмотра метрик MLX API Server
# Использование: bash scripts/check_mlx_status.sh

echo "═══════════════════════════════════════════════════════════════"
echo "🍎 MLX API Server - Метрики и статус"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Проверка доступности MLX
if ! curl -sf --connect-timeout 2 http://localhost:11435/health >/dev/null 2>&1; then
    echo "❌ MLX API Server недоступен на http://localhost:11435"
    echo "   Запустите: bash scripts/start_mlx_api_server.sh"
    exit 1
fi

echo "📊 Получение метрик..."
echo ""

# Получаем метрики через backend API (если доступен)
if curl -sf --connect-timeout 2 http://localhost:8080/api/chat/mlx/metrics >/dev/null 2>&1; then
    echo "✅ Используем backend API (http://localhost:8080/api/chat/mlx/metrics)"
    echo ""
    curl -s http://localhost:8080/api/chat/mlx/metrics | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8080/api/chat/mlx/metrics
else
    echo "⚠️  Backend недоступен, используем прямой доступ к MLX"
    echo ""
    curl -s http://localhost:11435/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:11435/health
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "💡 Быстрая проверка:"
echo "   curl http://localhost:11435/health | python3 -m json.tool"
echo "   curl http://localhost:8080/api/chat/mlx/metrics | python3 -m json.tool"
echo ""
