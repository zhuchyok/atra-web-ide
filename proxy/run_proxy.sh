#!/usr/bin/env bash
# Запуск прокси Claude Code → Victoria из корня репозитория.
# Использование: из корня atra-web-ide выполнить: ./proxy/run_proxy.sh

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
export VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
export PORT="${PORT:-8040}"
echo "VICTORIA_URL=$VICTORIA_URL PORT=$PORT"

VENV_DIR="$REPO_ROOT/proxy/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating venv in proxy/.venv ..."
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install -q -r proxy/requirements.txt
exec "$VENV_DIR/bin/python" -m uvicorn proxy.main:app --host 0.0.0.0 --port "$PORT"
