#!/bin/bash
# Автозапуск контейнеров корпорации ATRA
# Запускается после старта Docker Desktop
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:$PATH"

ensure_docker_network() {
    local name="$1"
    if docker network inspect "$name" >/dev/null 2>&1; then
        return 0
    fi
    if docker network create "$name" >/dev/null 2>&1; then
        return 0
    fi
    docker network inspect "$name" >/dev/null 2>&1
}

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

if ! ensure_docker_network "atra-network"; then
    echo "❌ Не удалось обеспечить сеть atra-network"
    exit 1
fi

# Запускаем контейнеры
echo "🚀 Запуск контейнеров корпорации ATRA..."
docker-compose -f knowledge_os/docker-compose.yml up -d db
sleep 5
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent veronica-agent knowledge_os_worker

# Проверяем Redis (отдельный контейнер, если нужен)
if ! docker ps --format '{{.Names}}' | grep -q '^atra-redis$'; then
    docker run -d --name atra-redis --network atra-network -p 6379:6379 redis:7-alpine
fi

FAIL=0
for name in victoria-agent veronica-agent; do
    if ! docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
        echo "❌ Контейнер не Up: $name"
        FAIL=1
    fi
done

if [ "$FAIL" -ne 0 ]; then
    echo "⚠️ Контейнеры запущены с ошибками"
    exit 1
fi

echo "✅ Контейнеры запущены"
