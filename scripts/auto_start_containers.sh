#!/bin/bash
# Автозапуск контейнеров корпорации ATRA
# Запускается после старта Docker Desktop

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Ждем пока Docker запустится
MAX_WAIT=60
WAITED=0
while ! docker info >/dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "⚠️ Docker не запустился за $MAX_WAIT секунд"
        exit 1
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

# Запускаем контейнеры
echo "🚀 Запуск контейнеров корпорации ATRA..."
docker-compose -f knowledge_os/docker-compose.yml up -d db
sleep 5
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent veronica-agent knowledge_os_api knowledge_os_worker 2>/dev/null || true

# Проверяем Redis
if ! docker ps | grep -q atra-redis; then
    docker run -d --name atra-redis --network atra-network -p 6379:6379 redis:7-alpine 2>/dev/null || true
fi

echo "✅ Контейнеры запущены"
