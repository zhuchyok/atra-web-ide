#!/usr/bin/env bash
# Запуск Streamlit дашборда локально (без Docker).
# Откройте http://localhost:8501

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT/knowledge_os/dashboard"

if ! python3 -c "import streamlit" 2>/dev/null; then
  echo "Установка зависимостей..."
  pip install -q streamlit pandas plotly psycopg2-binary networkx httpx
fi

echo "Запуск дашборда: http://localhost:8501"
exec python3 -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0
