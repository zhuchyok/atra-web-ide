#!/usr/bin/env bash
# Запуск UI-проверки дашборда (Playwright). При необходимости поднимает дашборд на 8501.
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/knowledge_os/.venv"
DASH="$ROOT/knowledge_os/dashboard"
PY="${VENV}/bin/python"
[ -x "$PY" ] || PY=python3

cd "$DASH"
"$PY" -m pip install -q playwright 2>/dev/null || true
"$PY" -m playwright install chromium 2>/dev/null || true
exec "$PY" verify_dashboard_ui.py
