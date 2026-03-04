#!/usr/bin/env bash
# Импорт узлов знаний из atra backups
# Источник: ~/Documents/dev/atra/backups/knowledge_os_*.sql.gz

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DUMP="$HOME/Documents/dev/atra/backups/knowledge_os_20260122_214735.sql.gz"

if [ ! -f "$DUMP" ]; then
  echo "❌ Дамп не найден: $DUMP"
  exit 1
fi

echo "📂 Дамп: $DUMP ($(ls -lh "$DUMP" | awk '{print $5}'))"
echo ""

# Вариант 1: через Docker (если backend запущен)
if docker ps --format "{{.Names}}" | grep -q atra-web-ide-backend 2>/dev/null; then
  echo "📥 Копируем дамп и скрипт в контейнер..."
  docker cp "$DUMP" atra-web-ide-backend:/tmp/kn_dump.sql.gz
  docker cp scripts/import_knowledge_from_atra_backup.py atra-web-ide-backend:/tmp/
  echo ""
  echo "⚠️  Импорт только INSERT — схема не меняется."
  echo "   Сначала проверка: DRY_RUN=1"
  docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
    -e ATRA_BACKUP_PATH=/tmp -e DRY_RUN=1 \
    atra-web-ide-backend python3 /tmp/import_knowledge_from_atra_backup.py
  echo ""
  if [ -z "$SKIP_CONFIRM" ]; then
    read -p "Продолжить импорт? (y/n): " ok
    if [ "$ok" != "y" ]; then
      echo "Отменено"
      exit 0
    fi
  fi
  echo "💾 Импорт (37k+ узлов, ~2-5 мин)..."
  docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
    -e ATRA_BACKUP_PATH=/tmp \
    atra-web-ide-backend python3 /tmp/import_knowledge_from_atra_backup.py
  echo "✅ Готово"
  exit 0
fi

# Вариант 2: локально (требует asyncpg)
echo "💾 Импорт (локально)..."
if [ -x "backend/.venv/bin/python" ]; then
  DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os \
    backend/.venv/bin/python scripts/import_knowledge_from_atra_backup.py
else
  echo "   pip install asyncpg"
  echo "   DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os python3 scripts/import_knowledge_from_atra_backup.py"
  exit 1
fi
