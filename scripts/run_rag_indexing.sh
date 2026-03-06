#!/usr/bin/env bash
# Запуск индексации COGNITIVE_CODE (и опционально других доков) в RAG. Для cron/launchd.
# Подхватывает .env из каталога проекта. Требуется DATABASE_URL и Ollama для эмбеддингов.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[ -f "$ROOT/.env" ] && set -a && source "$ROOT/.env" && set +a
export DATABASE_URL="${DATABASE_URL:-}"
if [ -x "$ROOT/knowledge_os/.venv/bin/python" ]; then
  exec "$ROOT/knowledge_os/.venv/bin/python" "$ROOT/knowledge_os/scripts/index_cognitive_code.py" "$@"
fi
exec python3 "$ROOT/knowledge_os/scripts/index_cognitive_code.py" "$@"
