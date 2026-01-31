#!/bin/bash
# Инициализация Victoria для нового проекта Cursor.
# Запускать при открытии нового проекта: bash scripts/init_victoria_for_new_project.sh

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "🤖 Инициализация Victoria для Cursor..."
echo ""

# Проверка Victoria
if curl -sf --connect-timeout 3 http://localhost:8010/health >/dev/null 2>&1; then
  echo "✅ Victoria работает (localhost:8010)"
else
  echo "⚠️  Victoria не отвечает. Запусти:"
  echo "   docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent"
  exit 1
fi

# Установка fastmcp
if ! python3 -c "import fastmcp" 2>/dev/null; then
  echo "📦 Установка fastmcp..."
  pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1
fi

# Запуск MCP сервера
if curl -sf --connect-timeout 3 http://localhost:8012/sse >/dev/null 2>&1; then
  echo "✅ MCP сервер уже работает (localhost:8012)"
else
  echo "🚀 Запуск MCP сервера..."
  export PYTHONPATH="$ROOT:$PYTHONPATH"
  nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
  sleep 2
  if curl -sf --connect-timeout 3 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "✅ MCP сервер запущен (PID: $!)"
  else
    echo "❌ Ошибка запуска. Лог: /tmp/victoria_mcp.log"
    exit 1
  fi
fi

echo ""
echo "📝 Настройка в Cursor:"
echo "   1. Settings (Cmd+,) → Features → MCP"
echo "   2. + Add New MCP Server"
echo "   3. Name: VictoriaATRA, Type: SSE, URL: http://localhost:8012/sse"
echo ""
echo "✅ Готово. Используй в чате: @victoria_run 'задача'"
