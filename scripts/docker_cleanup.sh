#!/bin/bash
# Очистка лишних Docker ресурсов для корпорации ATRA
# Безопасная очистка: удаляет только неиспользуемые ресурсы

set -e

echo "=============================================="
echo "🧹 Очистка Docker ресурсов"
echo "=============================================="
echo ""

# 1. Анализ текущего состояния
echo "[1/5] Анализ текущего состояния..."
echo ""

echo "📊 Использование дискового пространства:"
docker system df
echo ""

# 2. Удаление остановленных контейнеров
echo "[2/5] Удаление остановленных контейнеров..."
STOPPED=$(docker ps -a --filter "status=created" --filter "status=exited" -q)
if [ -z "$STOPPED" ]; then
    echo "   ✅ Нет остановленных контейнеров"
else
    echo "   Найдено остановленных контейнеров:"
    docker ps -a --filter "status=created" --filter "status=exited" --format "   - {{.Names}} ({{.Image}})"
    read -p "   Удалить? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rm $STOPPED
        echo "   ✅ Остановленные контейнеры удалены"
    else
        echo "   ⏭️  Пропущено"
    fi
fi
echo ""

# 3. Удаление неиспользуемых образов
echo "[3/5] Поиск неиспользуемых образов..."
UNUSED_IMAGES=$(docker images --filter "dangling=true" -q)
if [ -z "$UNUSED_IMAGES" ]; then
    echo "   ✅ Нет dangling образов"
else
    echo "   Найдено dangling образов:"
    docker images --filter "dangling=true" --format "   - {{.Repository}}:{{.Tag}} ({{.Size}})"
    read -p "   Удалить? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rmi $UNUSED_IMAGES
        echo "   ✅ Dangling образы удалены"
    else
        echo "   ⏭️  Пропущено"
    fi
fi
echo ""

# 4. Очистка build cache
echo "[4/5] Очистка build cache..."
CACHE_SIZE=$(docker system df | grep "Build Cache" | awk '{print $4}')
echo "   Размер build cache: $CACHE_SIZE"
read -p "   Очистить build cache? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker builder prune -f
    echo "   ✅ Build cache очищен"
else
    echo "   ⏭️  Пропущено"
fi
echo ""

# 5. Удаление неиспользуемых сетей
echo "[5/5] Поиск неиспользуемых сетей..."
UNUSED_NETWORKS=$(docker network ls --filter "dangling=true" -q)
if [ -z "$UNUSED_NETWORKS" ]; then
    echo "   ✅ Нет неиспользуемых сетей"
else
    echo "   Найдено неиспользуемых сетей:"
    docker network ls --filter "dangling=true" --format "   - {{.Name}}"
    read -p "   Удалить? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker network prune -f
        echo "   ✅ Неиспользуемые сети удалены"
    else
        echo "   ⏭️  Пропущено"
    fi
fi
echo ""

# Финальная статистика
echo "=============================================="
echo "📊 ФИНАЛЬНАЯ СТАТИСТИКА"
echo "=============================================="
docker system df
echo ""

echo "✅ Очистка завершена!"
echo ""
