#!/usr/bin/env bash
# Запустить НА Mac Studio (где postgres с тысячами узлов)
# Создаёт дамп knowledge_nodes для переноса в единую базу
#
# 1. На Mac Studio: bash scripts/export_knowledge_from_mac_studio.sh
# 2. Скопировать knowledge_nodes_dump.sql на локальную машину (scp, rsync)
# 3. Локально: docker exec -i knowledge_postgres psql -U admin -d knowledge_os < knowledge_nodes_dump.sql

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUTPUT="${1:-knowledge_nodes_dump.sql}"
echo "📤 Экспорт knowledge_nodes на Mac Studio..."

# Экспорт в custom format (лучше для переноса между разными схемами)
docker exec knowledge_postgres pg_dump -U admin -d knowledge_os \
  -t knowledge_nodes \
  --data-only \
  --format=custom \
  -f /tmp/kn_dump.dump 2>/dev/null && {
  docker cp knowledge_postgres:/tmp/kn_dump.dump "$OUTPUT"
  echo "✅ Дамп: $OUTPUT (custom format)"
  echo "   Импорт: pg_restore -U admin -d knowledge_os -t knowledge_nodes --data-only -h localhost $OUTPUT"
  exit 0
}

# Fallback: SQL
docker exec knowledge_postgres pg_dump -U admin -d knowledge_os \
  -t knowledge_nodes \
  --data-only \
  -f /tmp/kn_dump.sql 2>/dev/null && {
  docker cp knowledge_postgres:/tmp/kn_dump.sql "$OUTPUT"
  echo "✅ Дамп: $OUTPUT"
  exit 0
}

echo "❌ Ошибка. Проверьте: docker exec knowledge_postgres psql -U admin -d knowledge_os -c 'SELECT COUNT(*) FROM knowledge_nodes'"
exit 1
