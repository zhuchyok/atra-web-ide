#!/bin/bash
# Универсальный скрипт для автоматического подключения Victoria в ЛЮБОМ проекте.
# Работает автоматически при открытии проекта через .vscode/tasks.json

set -e

# Путь к ATRA / atra-web-ide (Mac Studio) — приоритет: atra-web-ide для работы по Mac Studio
ATRA_WEB_IDE="${HOME}/Documents/atra-web-ide"
ATRA_ROOT="${HOME}/Documents/GITHUB/atra/atra"
ATRA_ROOT_ALT="${HOME}/Documents/dev/atra"

# Определяем путь к проекту
if [ -d "$ATRA_WEB_IDE" ] && [ -f "$ATRA_WEB_IDE/src/agents/bridge/victoria_mcp_server.py" ]; then
  ROOT="$ATRA_WEB_IDE"
elif [ -d "$ATRA_ROOT" ]; then
  ROOT="$ATRA_ROOT"
elif [ -d "$ATRA_ROOT_ALT" ]; then
  ROOT="$ATRA_ROOT_ALT"
else
  # Пытаемся найти в текущем проекте
  ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
  if [ ! -f "$ROOT/src/agents/bridge/victoria_mcp_server.py" ]; then
    echo "⚠️  ATRA не найден. Пропуск Victoria."
    exit 0
  fi
fi

cd "$ROOT"

# 1. Проверка Victoria
if ! curl -sf --connect-timeout 2 http://localhost:8010/health >/dev/null 2>&1; then
  # Пытаемся запустить через Docker
  if command -v docker-compose >/dev/null 2>&1 && [ -f "$ROOT/knowledge_os/docker-compose.yml" ]; then
    docker-compose -f "$ROOT/knowledge_os/docker-compose.yml" up -d victoria-agent >/dev/null 2>&1 &
    sleep 3
  fi
fi

# 2. Проверка MCP сервера
if ! curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
  # Установка fastmcp
  if ! python3 -c "import fastmcp" 2>/dev/null; then
    pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1 || true
  fi
  
  # Запуск MCP сервера
  export PYTHONPATH="$ROOT:$PYTHONPATH"
  nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
  sleep 2
fi

# Всё готово (тихо, без вывода)
exit 0
