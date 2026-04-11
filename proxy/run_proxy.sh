#!/usr/bin/env bash
# Запуск прокси Claude Code → Victoria из корня репозитория.
# Использование: из корня atra-web-ide выполнить: ./proxy/run_proxy.sh
# ВАЖНО: venv расположен в ~/Library/ (не в Documents/) из-за macOS Sequoia TCC sandbox

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
export VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
export PORT="${PORT:-8040}"
echo "VICTORIA_URL=$VICTORIA_URL PORT=$PORT"

# Очищаем порт перед запуском (защита от EX_CONFIG при быстрых рестартах launchd)
PIDS_ON_PORT=$(lsof -ti:"$PORT" 2>/dev/null || true)
if [[ -n "$PIDS_ON_PORT" ]]; then
  echo "Порт $PORT занят (PID: $PIDS_ON_PORT) — освобождаем..."
  echo "$PIDS_ON_PORT" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# venv вне ~/Documents/ — macOS Sequoia TCC не блокирует ~/Library/
VENV_DIR="$HOME/Library/Application Support/atra/proxy-venv"
if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating venv in $VENV_DIR ..."
  mkdir -p "$HOME/Library/Application Support/atra/"
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -q -r "$REPO_ROOT/proxy/requirements.txt"
exec "$VENV_DIR/bin/python" -m uvicorn main:app --app-dir "$REPO_ROOT/proxy" --host 0.0.0.0 --port "$PORT" --log-level info
