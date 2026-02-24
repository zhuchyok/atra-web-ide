#!/bin/bash
# Импорт корневых контейнеров на Mac Studio
# Запускать на Mac Studio: bash scripts/import_root_containers.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Настройка PATH для Docker Desktop на Mac
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

echo "=============================================="
echo "📥 ИМПОРТ КОРНЕВЫХ КОНТЕЙНЕРОВ"
echo "=============================================="
echo ""

# Поиск последнего бэкапа корневых контейнеров
BACKUP_DIR=$(ls -td backups/migration/atra-root-migration-* 2>/dev/null | head -1)

if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Бэкап не найден!"
    echo "   Ожидается: backups/migration/atra-root-migration-*"
    echo ""
    echo "💡 Сначала выполните на MacBook:"
    echo "   bash scripts/migrate_root_containers.sh"
    exit 1
fi

echo "📁 Найден бэкап: $BACKUP_DIR"
echo ""

read -p "Продолжить импорт? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "Отменено"
    exit 0
fi

# 1. Проверка Docker
echo ""
echo "[1/4] Проверка Docker..."
if ! docker info &> /dev/null; then
    echo "   ❌ Docker daemon не запущен!"
    exit 1
fi
echo "   ✅ Docker готов"
echo ""

# 2. Импорт образов
echo "[2/4] Импорт Docker образов..."
IMAGE_FILES=$(find "$BACKUP_DIR" -name "*.tar.gz" -type f | grep -E "atra-web-ide" || true)
IMAGE_COUNT=0
for image_file in $IMAGE_FILES; do
    filename=$(basename "$image_file")
    echo "   Импорт образа: $filename"
    if docker load -i "$image_file" 2>&1 | grep -q "Loaded image"; then
        IMAGE_COUNT=$((IMAGE_COUNT + 1))
        echo "      ✅ Импортирован"
    else
        echo "      ⚠️  Ошибка или уже импортирован"
    fi
done
echo "   ✅ Импортировано образов: $IMAGE_COUNT"
echo ""

# 3. Импорт volumes
echo "[3/4] Импорт Docker volumes..."
VOLUME_FILES=$(find "$BACKUP_DIR" -name "*.tar.gz" -type f | grep -E "(atra-postgres-data|atra-redis-data|atra-workspace-data)" || true)
VOLUME_COUNT=0
for volume_file in $VOLUME_FILES; do
    volume_name=$(basename "$volume_file" .tar.gz)
    echo "   Импорт volume: $volume_name"

    if ! docker volume ls | grep -q "^${volume_name}$"; then
        docker volume create "$volume_name" 2>/dev/null || true
    fi

    docker run --rm -v "$volume_name":/data -v "$BACKUP_DIR":/backup alpine \
        sh -c "cd /data && tar xzf /backup/${volume_name}.tar.gz 2>&1" 2>/dev/null || true

    VOLUME_COUNT=$((VOLUME_COUNT + 1))
    echo "      ✅ Импортирован"
done
echo "   ✅ Импортировано volumes: $VOLUME_COUNT"
echo ""

# 4. Копирование конфигурации
echo "[4/4] Копирование конфигурации..."
if [ -f "$BACKUP_DIR/docker-compose.yml" ]; then
    cp "$BACKUP_DIR/docker-compose.yml" docker-compose.yml.macbook-backup
    echo "   ✅ Конфигурация сохранена как .macbook-backup"
fi
echo ""

echo "=============================================="
echo "✅ ИМПОРТ ЗАВЕРШЕН"
echo "=============================================="
echo ""
echo "💡 Для запуска контейнеров:"
echo "   docker-compose up -d"
echo ""
