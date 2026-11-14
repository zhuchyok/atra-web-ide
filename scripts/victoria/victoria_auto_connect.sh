#!/bin/bash
# Универсальный скрипт для автоматического подключения Victoria в ЛЮБОМ проекте.
# Работает автоматически при открытии проекта через .vscode/tasks.json

set -euo pipefail

ATRA_WEB_IDE="${HOME}/Documents/atra-web-ide"
ATRA_ROOT="${HOME}/Documents/GITHUB/atra/atra"
ATRA_ROOT_ALT="${HOME}/Documents/dev/atra"

if [ -d "$ATRA_WEB_IDE" ] && [ -f "$ATRA_WEB_IDE/src/agents/bridge/victoria_mcp_server.py" ]; then
  ROOT="$ATRA_WEB_IDE"
elif [ -d "$ATRA_ROOT" ]; then
  ROOT="$ATRA_ROOT"
elif [ -d "$ATRA_ROOT_ALT" ]; then
  ROOT="$ATRA_ROOT_ALT"
else
  ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
  if [ ! -f "$ROOT/src/agents/bridge/victoria_mcp_server.py" ]; then
    echo "⚠️  ATRA не найден. Пропуск Victoria."
    # Soft skip only when not in ATRA workspace (IDE task in foreign project)
    exit 0
  fi
fi

cd "$ROOT"
HARD_FAIL=0

# 1. Проверка Victoria (8010) — critical when ATRA found
if ! curl -sf --connect-timeout 2 http://localhost:8010/health >/dev/null 2>&1; then
  if command -v docker-compose >/dev/null 2>&1 && [ -f "$ROOT/knowledge_os/docker-compose.yml" ]; then
    docker-compose -f "$ROOT/knowledge_os/docker-compose.yml" up -d victoria-agent >/dev/null 2>&1 || true
    sleep 3
  fi
fi
if ! curl -sf --connect-timeout 2 http://localhost:8010/health >/dev/null 2>&1; then
  echo "❌ Victoria 8010 недоступна"
  HARD_FAIL=1
fi

# 2. MCP 8012 optional
if [ "${CHECK_LEGACY_MCP:-false}" = "true" ]; then
  if ! curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
    if ! python3 -c "import fastmcp" 2>/dev/null; then
      pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1 || true
    fi
    export PYTHONPATH="$ROOT:$PYTHONPATH"
    nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
    sleep 2
  fi
  if ! curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "❌ MCP 8012 недоступен"
    HARD_FAIL=1
  fi
fi

exit "$HARD_FAIL"
