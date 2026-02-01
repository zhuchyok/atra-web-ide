#!/usr/bin/env bash
# Проверка здоровья БД Knowledge OS (рекомендации экспертов после инцидента 2026-02-01)
# Минимальные пороги: experts >= 80, knowledge_nodes >= 10000
# Использование: ./scripts/verify_db_health.sh [--fail-on-warning]
set -e

FAIL_ON_WARNING=false
[ "$1" = "--fail-on-warning" ] && FAIL_ON_WARNING=true

MIN_EXPERTS=80
MIN_KNOWLEDGE_NODES=10000

echo "🔍 Проверка здоровья БД Knowledge OS..."
echo "   Пороги: experts >= $MIN_EXPERTS, knowledge_nodes >= $MIN_KNOWLEDGE_NODES"
echo ""

if ! docker ps --format '{{.Names}}' | grep -q '^knowledge_postgres$'; then
  echo "❌ Контейнер knowledge_postgres не запущен"
  exit 1
fi

COUNTS=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -A -c "
  SELECT (SELECT COUNT(*) FROM experts), (SELECT COUNT(*) FROM knowledge_nodes);
" 2>/dev/null) || {
  echo "❌ Не удалось выполнить запрос к БД"
  exit 1
}

EXPERTS=$(echo "$COUNTS" | cut -d'|' -f1 | tr -d ' ')
KNOWLEDGE=$(echo "$COUNTS" | cut -d'|' -f2 | tr -d ' ')

echo "   Экспертов: $EXPERTS"
echo "   Узлов знаний: $KNOWLEDGE"
echo ""

OK=true
if [ "${EXPERTS:-0}" -lt "$MIN_EXPERTS" ]; then
  echo "⚠️  ВНИМАНИЕ: экспертов ($EXPERTS) меньше порога ($MIN_EXPERTS). Возможно переключение volume (см. docs/INCIDENT_DB_VOLUME_SWITCH_2026_02_01.md)"
  OK=false
fi
if [ "${KNOWLEDGE:-0}" -lt "$MIN_KNOWLEDGE_NODES" ]; then
  echo "⚠️  ВНИМАНИЕ: узлов знаний ($KNOWLEDGE) меньше порога ($MIN_KNOWLEDGE_NODES). Возможно переключение volume."
  OK=false
fi

if [ "$OK" = true ]; then
  echo "✅ БД в норме"
  exit 0
fi

if [ "$FAIL_ON_WARNING" = true ]; then
  echo ""
  echo "Завершение с ошибкой (--fail-on-warning)"
  exit 1
fi

exit 0
