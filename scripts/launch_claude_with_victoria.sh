#!/usr/bin/env bash
# Запуск прокси Victoria (8040) и Claude Code с папкой OLL — чат идёт в Викторию.
# Использование: ./scripts/launch_claude_with_victoria.sh
# По завершении Claude Code прокси останавливается.

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OLL_DIR="${OLL_DIR:-/Users/bikos/Documents/OLL}"
PORT="${PORT:-8040}"
VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"

cd "$REPO_ROOT"

PROXY_PID=""
cleanup() {
  if [[ -n "$PROXY_PID" ]]; then
    echo "Stopping proxy (PID $PROXY_PID)..."
    kill "$PROXY_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Проверка и очистка порта перед запуском
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
  echo "Port $PORT is already in use. Checking if it's our proxy..."
  if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null | grep -q 200; then
    echo "Proxy already running on port $PORT, using it."
    # Пытаемся найти PID уже запущенного прокси для корректного cleanup
    PROXY_PID=$(lsof -ti :$PORT)
  else
    echo "Port $PORT is occupied by another process. Cleaning up..."
    lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
fi

if ! lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
  echo "Starting proxy on port $PORT (Victoria: $VICTORIA_URL)..."
  ./proxy/run_proxy.sh &
  PROXY_PID=$!
  for i in {1..15}; do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null | grep -q 200; then
      echo "Proxy ready."
      break
    fi
    if [[ $i -eq 15 ]]; then
      echo "Proxy did not start in time. Check Victoria on $VICTORIA_URL and port $PORT."
      exit 1
    fi
    sleep 1
  done
fi

# Проверка и добавление Victoria MCP в Claude Code (если ещё не добавлен)
if ! claude mcp list | grep -q "VictoriaATRA"; then
  echo "Adding VictoriaATRA MCP server to Claude Code..."
  # В Claude Code синтаксис: claude mcp add <name> <command> [args...]
  PYTHON_BIN="$REPO_ROOT/proxy/.venv/bin/python"
  if [[ ! -f "$PYTHON_BIN" ]]; then PYTHON_BIN="python3"; fi
  # Используем -- для отделения аргументов команды от аргументов claude
  claude mcp add VictoriaATRA -- "$PYTHON_BIN" -m src.agents.bridge.victoria_mcp_server
fi

# Claude Code с env для прокси
export ANTHROPIC_BASE_URL="http://localhost:$PORT"
export ANTHROPIC_API_KEY="sk-ant-api03-placeholder-for-local-proxy"
# Отключаем проверку обновлений и телеметрию для полной автономности
export CLAUDE_CODE_DISABLE_UPDATE_CHECK=1
export CLAUDE_CODE_OPT_OUT_TELEMETRY=1

# Если OLL_DIR не существует, используем корень репозитория
if [[ ! -d "$OLL_DIR" ]]; then
  echo "⚠️ Warning: OLL_DIR ($OLL_DIR) not found. Using REPO_ROOT ($REPO_ROOT) instead."
  OLL_DIR="$REPO_ROOT"
fi

cd "$OLL_DIR"
echo "🚀 Launching OpenClaude (workspace: $OLL_DIR, backend: Victoria via proxy)..."
echo "   - Proxy: http://localhost:$PORT"
echo "   - Victoria: $VICTORIA_URL"
claude launch
