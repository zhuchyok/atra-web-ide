#!/usr/bin/env bash
# Запуск Streamlit дашборда локально (без Docker).
# Откройте http://localhost:8501

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DASH="$ROOT/knowledge_os/dashboard"
VENV="$ROOT/knowledge_os/.venv"

cd "$DASH"
PYTHON="python3"
if [ -x "$VENV/bin/python" ]; then
  PYTHON="$VENV/bin/python"
  if ! $PYTHON -c "import streamlit" 2>/dev/null; then
    echo "Установка зависимостей в venv..."
    $PYTHON -m pip install -q streamlit pandas plotly psycopg2-binary networkx httpx
  fi
elif ! python3 -c "import streamlit" 2>/dev/null; then
  echo "Установка зависимостей (рекомендуется: bash knowledge_os/scripts/setup_knowledge_os.sh для venv)..."
  python3 -m pip install -q streamlit pandas plotly psycopg2-binary networkx httpx 2>/dev/null || true
fi

echo "Запуск дашборда: http://localhost:8501"
exec $PYTHON -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0
