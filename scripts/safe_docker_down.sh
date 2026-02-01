#!/usr/bin/env bash
# Безопасная остановка Docker — защита от случайного down -v (рекомендации экспертов 2026-02-01)
# Использование: ./scripts/safe_docker_down.sh [--force]
# БЕЗ -v: volumes сохраняются (рекомендуется)
# С -v: только с явным --force и подтверждением
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FORCE=false
REMOVE_VOLUMES=false
for arg in "$@"; do
  [ "$arg" = "--force" ] && FORCE=true
  [ "$arg" = "-v" ] && REMOVE_VOLUMES=true
done

if [ "$REMOVE_VOLUMES" = true ]; then
  echo "⚠️  ВНИМАНИЕ: Вы запросили остановку С УДАЛЕНИЕМ VOLUMES (-v)"
  echo ""
  echo "   Это УДАЛИТ данные PostgreSQL (experts, knowledge_nodes, tasks)!"
  echo "   Volume atra_knowledge_postgres_data содержит 85+ экспертов и 26k+ узлов знаний."
  echo ""
  echo "   См. docs/INCIDENT_DB_VOLUME_SWITCH_2026_02_01.md"
  echo ""
  if [ "$FORCE" != true ]; then
    echo "   Для продолжения: ./scripts/safe_docker_down.sh -v --force"
    exit 1
  fi
  read -p "   Введите 'DELETE VOLUMES' для подтверждения: " confirm
  if [ "$confirm" != "DELETE VOLUMES" ]; then
    echo "   Отменено."
    exit 1
  fi
fi

echo "Остановка контейнеров..."
docker-compose -f knowledge_os/docker-compose.yml down "$@"
echo "✅ Готово"
