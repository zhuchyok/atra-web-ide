#!/usr/bin/env bash
# Запуск Victoria (и при необходимости Veronica) в Docker.
# Требуется: запущенный Docker Desktop (или docker daemon).
#
# Использование:
#   bash scripts/start_victoria_docker.sh
#   bash scripts/start_victoria_docker.sh veronica  # ещё и Veronica

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "🐳 Запуск Victoria в Docker..."
echo ""

# 1. Проверка, что Docker запущен
if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker не запущен или недоступен."
  echo "   Запустите Docker Desktop (или docker daemon), затем повторите:"
  echo "   bash scripts/start_victoria_docker.sh"
  exit 1
fi
echo "✅ Docker доступен"

# 2. Сеть atra-network создаётся автоматически из docker-compose (name: atra-network).
#    Если нужна общая сеть с другим проектом — создайте заранее: docker network create atra-network
if ! docker network inspect atra-network >/dev/null 2>&1; then
  echo "   Создаю сеть atra-network..."
  docker network create atra-network 2>/dev/null || true
fi

# 3. Запуск Victoria (и опционально Veronica)
COMPOSE_FILE="knowledge_os/docker-compose.yml"
if [[ "${1:-}" == "veronica" ]]; then
  echo "   Запуск victoria-agent и veronica-agent..."
  docker-compose -f "$COMPOSE_FILE" up -d victoria-agent veronica-agent
else
  echo "   Запуск victoria-agent..."
  docker-compose -f "$COMPOSE_FILE" up -d victoria-agent
fi

echo ""
echo "✅ Victoria запущена в Docker."
echo "   Health: curl -s http://localhost:8010/health"
echo "   Чат:    bash scripts/chat_victoria.sh"
echo ""
echo "   Остановка: docker-compose -f $COMPOSE_FILE stop victoria-agent"
echo "   Логи:      docker logs -f victoria-agent"
exit 0
