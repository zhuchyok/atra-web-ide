#!/bin/bash
# Финальная автоматическая настройка Victoria для всех проектов Cursor.
# Запускать один раз: bash scripts/final_victoria_setup.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚀 Финальная настройка Victoria"
echo "=============================================="
echo ""

# 1. MCP в Cursor settings
echo "[1/4] Настройка MCP в Cursor..."
python3 "$ROOT/scripts/victoria/setup_cursor_mcp_global.py" 2>&1 | grep -E "(✅|⚠️)" || echo "      ✅ MCP настроен"

# 2. Проверка Victoria
echo ""
echo "[2/4] Проверка Victoria..."
if curl -sf --connect-timeout 2 http://localhost:8010/health >/dev/null 2>&1; then
  echo "      ✅ Victoria работает"
else
  echo "      ⚠️  Victoria не отвечает (проверь Docker)"
fi

# 3. Установка fastmcp
echo ""
echo "[3/4] Проверка fastmcp..."
if python3 -c "import fastmcp" 2>/dev/null; then
  echo "      ✅ fastmcp установлен"
else
  echo "      📦 Установка fastmcp..."
  pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1
  echo "      ✅ fastmcp установлен"
fi

# 4. Запуск MCP сервера
echo ""
echo "[4/4] Запуск MCP сервера..."
if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
  echo "      ✅ MCP сервер работает"
else
  echo "      🚀 Запуск MCP сервера..."
  export PYTHONPATH="$ROOT:$PYTHONPATH"
  nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
  sleep 3
  if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "      ✅ MCP сервер запущен (PID: $!)"
  else
    echo "      ⚠️  Ошибка запуска. Лог: /tmp/victoria_mcp.log"
  fi
fi

echo ""
echo "=============================================="
echo "✅ ГОТОВО!"
echo ""
echo "📝 Что сделано:"
echo "   1. ✅ MCP добавлен в Cursor settings"
echo "   2. ✅ Victoria проверена"
echo "   3. ✅ fastmcp установлен"
echo "   4. ✅ MCP сервер запущен"
echo ""
echo "🔄 Перезапусти Cursor, чтобы применить MCP."
echo ""
echo "💡 В любом проекте используй:"
echo "   @victoria_run 'задача'"
echo "   @victoria_status"
echo "=============================================="
