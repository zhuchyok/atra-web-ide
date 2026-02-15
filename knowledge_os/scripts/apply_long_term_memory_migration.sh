#!/usr/bin/env bash
# Применить только миграцию долгосрочной памяти (Фаза 2 плана «Логика мысли»).
# Требуется: PostgreSQL Knowledge OS (DATABASE_URL или дефолт postgresql://admin:secret@localhost:5432/knowledge_os).
#
# Варианты:
#   cd knowledge_os && ./scripts/apply_long_term_memory_migration.sh
#   DATABASE_URL=postgresql://user:pass@host:5432/knowledge_os ./scripts/apply_long_term_migration.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATION_FILE="$KO_ROOT/db/migrations/add_long_term_memory.sql"

if [ ! -f "$MIGRATION_FILE" ]; then
  echo "❌ Файл миграции не найден: $MIGRATION_FILE"
  exit 1
fi

# Применить все неприменённые миграции (включая add_long_term_memory.sql)
cd "$KO_ROOT"
if [ -x ".venv/bin/python" ]; then
  .venv/bin/python scripts/apply_migrations.py
else
  python3 scripts/apply_migrations.py
fi
echo "✅ Готово. Долгосрочная память: таблица long_term_memory будет создана при первом применении миграций."
