#!/bin/bash
# Миграция Docker контейнеров с MacBook на Mac Studio
# Запускать на MacBook: bash scripts/migrate_docker_to_mac_studio.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚚 МИГРАЦИЯ DOCKER С MACBOOK НА MAC STUDIO"
echo "=============================================="
echo ""

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "📋 План миграции:"
echo "   1. Остановка контейнеров на MacBook"
echo "   2. Экспорт данных (volumes, базы данных)"
echo "   3. Копирование на Mac Studio"
echo ""

read -p "Продолжить? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Отменено"
    exit 0
fi

# 1. Проверка подключения к Mac Studio
echo ""
echo "[1/4] Проверка подключения к Mac Studio..."
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo 'OK'" 2>/dev/null; then
    echo "   ❌ Не удалось подключиться к Mac Studio"
    echo "   💡 Убедитесь, что Mac Studio включен и в сети"
    exit 1
fi
echo "   ✅ Подключение установлено"
echo ""

# 2. Остановка контейнеров
echo "[2/4] Остановка контейнеров на MacBook..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    echo "   Остановка knowledge_os контейнеров..."
    docker-compose -f knowledge_os/docker-compose.yml down
    echo "   ✅ Knowledge OS контейнеры остановлены"
fi
if [ -f "docker-compose.yml" ]; then
    echo "   Остановка корневых контейнеров..."
    docker-compose down 2>/dev/null || true
    echo "   ✅ Корневые контейнеры остановлены"
fi
echo ""

# 3. Экспорт volumes и контейнеров
echo "[3/4] Экспорт Docker volumes и контейнеров..."
BACKUP_DIR="/tmp/atra-docker-migration-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Экспорт ВСЕХ volumes (не только atra/knowledge/postgres)
echo "   Поиск всех Docker volumes..."
ALL_VOLUMES=$(docker volume ls --format "{{.Name}}" || true)
if [ -n "$ALL_VOLUMES" ]; then
    VOLUME_COUNT=0
    for volume in $ALL_VOLUMES; do
        # Пропускаем системные volumes
        if [[ "$volume" =~ ^(bridge|host|none)$ ]]; then
            continue
        fi
        echo "   Экспорт volume: $volume"
        docker run --rm -v "$volume":/data -v "$BACKUP_DIR":/backup alpine \
            sh -c "cd /data && tar czf /backup/${volume}.tar.gz . 2>&1" || {
            echo "      ⚠️  Ошибка экспорта $volume (может быть пустым)"
        }
        VOLUME_COUNT=$((VOLUME_COUNT + 1))
    done
    echo "   ✅ Экспортировано volumes: $VOLUME_COUNT"
else
    echo "   ⚠️  Volumes не найдены"
fi

# Экспорт образов (images)
echo "   Экспорт Docker образов..."
IMAGES=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "atra|knowledge|victoria|veronica|postgres" || true)
if [ -n "$IMAGES" ]; then
    IMAGE_COUNT=0
    for image in $IMAGES; do
        if [[ "$image" == "<none>:<none>" ]]; then
            continue
        fi
        echo "   Экспорт образа: $image"
        IMAGE_FILE=$(echo "$image" | tr '/:' '_')
        docker save "$image" | gzip > "$BACKUP_DIR/${IMAGE_FILE}.tar.gz" 2>&1 || {
            echo "      ⚠️  Ошибка экспорта образа $image"
        }
        IMAGE_COUNT=$((IMAGE_COUNT + 1))
    done
    echo "   ✅ Экспортировано образов: $IMAGE_COUNT"
else
    echo "   ⚠️  Образы не найдены"
fi

# Копирование конфигурации
echo "   Копирование конфигурации..."
cp knowledge_os/docker-compose.yml "$BACKUP_DIR/" 2>/dev/null || true
cp docker-compose.yml "$BACKUP_DIR/" 2>/dev/null || true
cp .env* "$BACKUP_DIR/" 2>/dev/null || true
find . -maxdepth 2 -name "*.env*" -exec cp {} "$BACKUP_DIR/" \; 2>/dev/null || true
echo "   ✅ Конфигурация скопирована"

# Создание списка volumes и образов
echo "$ALL_VOLUMES" > "$BACKUP_DIR/volumes.list" 2>/dev/null || true
echo "$IMAGES" > "$BACKUP_DIR/images.list" 2>/dev/null || true
echo ""

# 4. Копирование на Mac Studio
echo "[4/4] Копирование на Mac Studio..."
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "mkdir -p ${MAC_STUDIO_PATH}/backups/migration" 2>/dev/null || true
scp -r "$BACKUP_DIR" ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backups/migration/ 2>/dev/null || {
    echo "   ❌ Ошибка копирования"
    echo "   💡 Скопируйте вручную: scp -r $BACKUP_DIR ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backups/migration/"
    exit 1
}
echo "   ✅ Файлы скопированы"
echo ""

echo "=============================================="
echo "✅ ЭКСПОРТ ЗАВЕРШЕН"
echo "=============================================="
echo ""
echo "📋 СЛЕДУЮЩИЕ ШАГИ НА MAC STUDIO:"
echo "   1. cd ~/Documents/atra-web-ide"
echo "   2. bash scripts/import_docker_from_macbook.sh"
echo ""
echo "📁 Данные: $BACKUP_DIR"
echo ""
