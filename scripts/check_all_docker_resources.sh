#!/bin/bash
# Полная проверка всех Docker ресурсов на MacBook
# Запускать: bash scripts/check_all_docker_resources.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🔍 ПОЛНАЯ ПРОВЕРКА DOCKER РЕСУРСОВ"
echo "=============================================="
echo ""

# 1. Контейнеры
echo "[1/4] КОНТЕЙНЕРЫ:"
echo "----------------------------------------"
ALL_CONTAINERS=$(docker ps -a --format "{{.Names}}" 2>/dev/null || echo "")
if [ -n "$ALL_CONTAINERS" ]; then
    echo "Всего контейнеров: $(echo "$ALL_CONTAINERS" | wc -l | tr -d ' ')"
    echo ""
    docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" 2>&1
else
    echo "   Контейнеры не найдены"
fi
echo ""

# 2. Образы
echo "[2/4] ОБРАЗЫ:"
echo "----------------------------------------"
ALL_IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" 2>/dev/null || echo "")
if [ -n "$ALL_IMAGES" ]; then
    echo "Всего образов: $(echo "$ALL_IMAGES" | wc -l | tr -d ' ')"
    echo ""
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" 2>&1 | head -20
    echo ""
    echo "   ... (показаны первые 20)"
else
    echo "   Образы не найдены"
fi
echo ""

# 3. Volumes
echo "[3/4] VOLUMES:"
echo "----------------------------------------"
ALL_VOLUMES=$(docker volume ls --format "{{.Name}}" 2>/dev/null || echo "")
if [ -n "$ALL_VOLUMES" ]; then
    echo "Всего volumes: $(echo "$ALL_VOLUMES" | wc -l | tr -d ' ')"
    echo ""
    for volume in $ALL_VOLUMES; do
        if [[ "$volume" =~ ^(bridge|host|none)$ ]]; then
            continue
        fi
        SIZE=$(docker volume inspect "$volume" 2>/dev/null | grep -o '"Mountpoint"[^,]*' | cut -d'"' -f4 | xargs du -sh 2>/dev/null | cut -f1 || echo "неизвестно")
        echo "   - $volume ($SIZE)"
    done
else
    echo "   Volumes не найдены"
fi
echo ""

# 4. Networks
echo "[4/4] СЕТИ:"
echo "----------------------------------------"
ALL_NETWORKS=$(docker network ls --format "{{.Name}}" 2>/dev/null | grep -vE "^(bridge|host|none)$" || echo "")
if [ -n "$ALL_NETWORKS" ]; then
    echo "Всего сетей (кроме системных): $(echo "$ALL_NETWORKS" | wc -l | tr -d ' ')"
    echo ""
    docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" 2>&1 | grep -vE "^(bridge|host|none)"
else
    echo "   Сети не найдены"
fi
echo ""

# 5. Docker Compose сервисы
echo "[5/5] DOCKER COMPOSE СЕРВИСЫ:"
echo "----------------------------------------"
if [ -f "docker-compose.yml" ]; then
    echo "Корневой docker-compose.yml:"
    docker-compose ps 2>&1 | grep -v "level=warning" || echo "   Нет запущенных сервисов"
    echo ""
fi

if [ -f "knowledge_os/docker-compose.yml" ]; then
    echo "knowledge_os/docker-compose.yml:"
    docker-compose -f knowledge_os/docker-compose.yml ps 2>&1 | grep -v "level=warning" || echo "   Нет запущенных сервисов"
fi
echo ""

echo "=============================================="
echo "✅ ПРОВЕРКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "💡 Для миграции на Mac Studio используйте:"
echo "   bash scripts/full_migration_macbook_to_macstudio.sh"
echo ""
