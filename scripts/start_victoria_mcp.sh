#!/bin/bash
# Запуск Victoria MCP Server для Cursor (порт 8012)
# Использование: ./scripts/start_victoria_mcp.sh
cd "$(dirname "$0")/.."

VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
export VICTORIA_URL

# Проверка: Victoria Agent на 8010
if ! curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://localhost:8010/health" 2>/dev/null | grep -q 200; then
    echo "⚠️ Victoria Agent (8010) не отвечает. Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent"
fi

# Используем backend venv (fastmcp)
PYTHON="${PYTHON:-backend/.venv/bin/python3}"
if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi

echo "🚀 Victoria MCP Server (порт 8012) → Victoria $VICTORIA_URL"
echo "   Cursor SSE: http://localhost:8012/sse"
echo "   Ctrl+C для остановки"
echo ""

exec "$PYTHON" -m src.agents.bridge.victoria_mcp_server
