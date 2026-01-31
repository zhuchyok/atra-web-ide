#!/bin/bash
# Автоматическая настройка подключения Victoria к Cursor при открытии проекта.
# Запускать из корня проекта: bash scripts/setup_victoria_cursor.sh

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CURSOR_SETTINGS="${HOME}/Library/Application Support/Cursor/User/settings.json"
MCP_CONFIG_DIR="${HOME}/Library/Application Support/Cursor/User/globalStorage"

echo "=============================================="
echo "Настройка Victoria для Cursor"
echo "=============================================="
echo ""

# 1. Проверка Victoria
echo "[1/3] Проверка Victoria (localhost:8010)..."
if curl -sf --connect-timeout 3 http://localhost:8010/health >/dev/null 2>&1; then
  echo "      ✅ Victoria работает"
else
  echo "      ⚠️  Victoria не отвечает. Убедись, что Docker запущен и victoria-agent работает."
  echo "      Запуск: docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent"
fi

# 2. Проверка зависимостей
echo ""
echo "[2/4] Проверка зависимостей..."
if python3 -c "import fastmcp" 2>/dev/null; then
  echo "      ✅ fastmcp установлен"
else
  echo "      Установка fastmcp..."
  pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1 || {
    echo "      ⚠️  Не удалось установить fastmcp. Установи вручную: pip3 install fastmcp"
  }
fi

# 3. Запуск MCP сервера (если не запущен)
echo ""
echo "[3/4] MCP сервер Victoria (localhost:8012)..."
if curl -sf --connect-timeout 3 http://localhost:8012/sse >/dev/null 2>&1; then
  echo "      ✅ MCP сервер уже работает"
else
  echo "      Запуск MCP сервера в фоне..."
  cd "$ROOT"
  export PYTHONPATH="$ROOT:$PYTHONPATH"
  nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
  MCP_PID=$!
  sleep 3
  if curl -sf --connect-timeout 3 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "      ✅ MCP сервер запущен (PID: $MCP_PID)"
    echo "      Лог: /tmp/victoria_mcp.log"
  else
    echo "      ⚠️  Не удалось запустить MCP сервер. Лог: /tmp/victoria_mcp.log"
    tail -20 /tmp/victoria_mcp.log 2>/dev/null || true
  fi
fi

# 4. Инструкция для Cursor
echo ""
echo "[4/4] Настройка в Cursor:"
echo ""
echo "  1. Открой Cursor Settings (Cmd+,)"
echo "  2. Features → MCP"
echo "  3. + Add New MCP Server"
echo "  4. Введи:"
echo "     Name: VictoriaATRA"
echo "     Type: SSE"
echo "     URL: http://localhost:8012/sse"
echo ""
echo "  Или добавь в settings.json:"
echo ""
cat << 'EOF'
  "mcp.servers": {
    "VictoriaATRA": {
      "type": "sse",
      "url": "http://localhost:8012/sse"
    }
  }
EOF

echo ""
echo "=============================================="
echo "Готово. После настройки MCP в Cursor используй:"
echo "  @victoria_run 'твоя задача'"
echo "  @victoria_status"
echo "=============================================="
