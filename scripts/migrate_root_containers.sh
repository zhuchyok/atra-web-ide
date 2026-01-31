#!/bin/bash
# Миграция контейнеров из корневого docker-compose.yml
# Запускать на MacBook: bash scripts/migrate_root_containers.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "=============================================="
echo "🚚 МИГРАЦИЯ КОРНЕВЫХ КОНТЕЙНЕРОВ"
echo "=============================================="
echo ""
echo "📋 Найдены контейнеры из корневого docker-compose.yml:"
echo "   - frontend (atra-web-ide-frontend)"
echo "   - backend (atra-web-ide-backend)"
echo "   - victoria (atra-victoria-agent)"
echo "   - veronica (atra-veronica-agent)"
echo "   - db (atra-knowledge-os-db)"
echo "   - redis (atra-redis)"
echo ""

read -p "Продолжить миграцию? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Отменено"
    exit 0
fi

# 1. Проверка подключения
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
echo "[2/4] Остановка корневых контейнеров..."
if [ -f "docker-compose.yml" ]; then
    docker-compose down 2>/dev/null || true
    echo "   ✅ Контейнеры остановлены"
else
    echo "   ⚠️  docker-compose.yml не найден"
fi
echo ""

# 3. Экспорт volumes и образов
echo "[3/4] Экспорт данных..."
BACKUP_DIR="/tmp/atra-root-migration-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Экспорт volumes из корневого docker-compose.yml
ROOT_VOLUMES="atra-postgres-data atra-redis-data atra-workspace-data"
VOLUME_COUNT=0
for volume in $ROOT_VOLUMES; do
    if docker volume ls | grep -q "^${volume}$"; then
        echo "   Экспорт volume: $volume"
        docker run --rm -v "$volume":/data -v "$BACKUP_DIR":/backup alpine \
            sh -c "cd /data && tar czf /backup/${volume}.tar.gz . 2>&1" || true
        VOLUME_COUNT=$((VOLUME_COUNT + 1))
    fi
done
echo "   ✅ Экспортировано volumes: $VOLUME_COUNT"

# Экспорт образов из корневого docker-compose.yml
ROOT_IMAGES="atra-web-ide-frontend:latest atra-web-ide-backend:latest atra-web-ide-victoria:latest atra-web-ide-veronica:latest"
IMAGE_COUNT=0
for image in $ROOT_IMAGES; do
    if docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${image}$"; then
        echo "   Экспорт образа: $image"
        IMAGE_FILE=$(echo "$image" | tr '/:' '_')
        docker save "$image" | gzip > "$BACKUP_DIR/${IMAGE_FILE}.tar.gz" 2>&1 || true
        IMAGE_COUNT=$((IMAGE_COUNT + 1))
    fi
done
echo "   ✅ Экспортировано образов: $IMAGE_COUNT"

# Копирование конфигурации
cp docker-compose.yml "$BACKUP_DIR/" 2>/dev/null || true
echo "   ✅ Конфигурация скопирована"
echo ""

# 4. Копирование на Mac Studio
echo "[4/4] Копирование на Mac Studio..."
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "mkdir -p ${MAC_STUDIO_PATH}/backups/migration" 2>/dev/null || true
scp -r "$BACKUP_DIR" ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backups/migration/ 2>&1 || {
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
echo "   2. bash scripts/import_root_containers.sh"
echo ""
echo "📁 Данные: $BACKUP_DIR"
echo ""
