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

# Если прокси уже слушает порт — не поднимаем второй
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null | grep -q 200; then
  echo "Proxy already running on port $PORT, using it."
else
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

# Claude Code с env для прокси
export ANTHROPIC_BASE_URL="http://localhost:$PORT"
export ANTHROPIC_API_KEY="sk-ant-api03-placeholder-for-local-proxy"
cd "$OLL_DIR"
echo "Launching Claude Code (workspace: $OLL_DIR, backend: Victoria via proxy)..."
claude launch
