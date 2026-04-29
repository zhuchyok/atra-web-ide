#!/usr/bin/env bash
set -e

PROXY_DIR="/Users/bikos/Documents/atra-web-ide/proxy"
VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
PORT="${PORT:-8040}"

echo "$(date): Starting Victoria Proxy from $PROXY_DIR on port $PORT"

lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
sleep 1

cd "$PROXY_DIR"
exec python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" --log-level info