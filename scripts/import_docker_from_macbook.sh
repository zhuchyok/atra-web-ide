#!/bin/bash
# Импорт Docker контейнеров с MacBook на Mac Studio
# Запускать на Mac Studio: bash scripts/import_docker_from_macbook.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "📥 ИМПОРТ DOCKER С MACBOOK НА MAC STUDIO"
echo "=============================================="
echo ""

# Поиск последнего бэкапа
BACKUP_DIR=$(ls -td backups/migration/atra-docker-migration-* 2>/dev/null | head -1)

if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Бэкап не найден!"
    echo "   Ожидается: backups/migration/atra-docker-migration-*"
    echo ""
    echo "💡 Сначала выполните на MacBook:"
    echo "   bash scripts/migrate_docker_to_mac_studio.sh"
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

# Настройка PATH для Docker Desktop на Mac
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

# Проверка наличия docker
if ! command -v docker &> /dev/null; then
    # Попытка найти docker в стандартных местах
    if [ -f "/Applications/Docker.app/Contents/Resources/bin/docker" ]; then
        export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
    elif [ -f "/usr/local/bin/docker" ]; then
        export PATH="/usr/local/bin:$PATH"
    else
        echo "   ❌ Docker не найден!"
        echo "   💡 Убедитесь, что Docker Desktop установлен и запущен"
        exit 1
    fi
fi

if ! docker info &> /dev/null; then
    echo "   ❌ Docker daemon не запущен!"
    echo "   💡 Запустите Docker Desktop и дождитесь полного запуска"
    exit 1
fi
echo "   ✅ Docker готов"
echo ""

# 2. Создание сети
echo "[2/4] Создание Docker сети..."
if ! docker network ls | grep -q atra-network; then
    docker network create atra-network
    echo "   ✅ Сеть atra-network создана"
else
    echo "   ✅ Сеть atra-network уже существует"
fi
echo ""

# 3. Импорт образов (images)
echo "[3/5] Импорт Docker образов..."
# Находим файлы образов (они обычно содержат двоеточие в имени или не являются volumes)
IMAGE_FILES=$(find "$BACKUP_DIR" -name "*.tar.gz" -type f | grep -vE "(atra-|knowledge_os_|postgres|redis|workspace|elasticsearch|grafana|prometheus).*\.tar\.gz$" || true)

if [ -z "$IMAGE_FILES" ]; then
    # Альтернативный поиск: файлы с подчеркиваниями и двоеточиями (образы обычно так называются)
    IMAGE_FILES=$(find "$BACKUP_DIR" -name "*_latest.tar.gz" -type f || true)
fi

if [ -n "$IMAGE_FILES" ]; then
    IMAGE_COUNT=0
    for image_file in $IMAGE_FILES; do
        filename=$(basename "$image_file")
        # Пропускаем volumes (они обычно без подчеркиваний или с определенными именами)
        if [[ "$filename" =~ ^(atra-|knowledge_os_|postgres|redis|workspace|elasticsearch|grafana|prometheus) ]]; then
            continue
        fi
        echo "   Импорт образа: $filename"
        if docker load -i "$image_file" 2>&1 | grep -q "Loaded image"; then
            IMAGE_COUNT=$((IMAGE_COUNT + 1))
            echo "      ✅ Импортирован"
        else
            echo "      ⚠️  Ошибка или уже импортирован"
        fi
    done
    if [ $IMAGE_COUNT -gt 0 ]; then
        echo "   ✅ Импортировано образов: $IMAGE_COUNT"
    else
        echo "   ⚠️  Образы не найдены или уже импортированы"
    fi
else
    echo "   ⚠️  Файлы образов не найдены"
fi
echo ""

# 4. Импорт volumes
echo "[4/5] Импорт Docker volumes..."

# Находим файлы volumes (они обычно имеют имена volumes)
VOLUME_FILES=$(find "$BACKUP_DIR" -name "*.tar.gz" -type f | grep -E "(atra-|knowledge_os_|postgres|redis|workspace|elasticsearch|grafana|prometheus).*\.tar\.gz$" || true)

if [ -z "$VOLUME_FILES" ] && [ -f "$BACKUP_DIR/volumes.list" ]; then
    # Используем список volumes из файла
    VOLUMES_LIST=$(cat "$BACKUP_DIR/volumes.list" | grep -v "^$" | grep -vE "^(bridge|host|none)$" || true)
    VOLUME_FILES=""
    for vol_name in $VOLUMES_LIST; do
        if [ -f "$BACKUP_DIR/${vol_name}.tar.gz" ]; then
            VOLUME_FILES="$VOLUME_FILES $BACKUP_DIR/${vol_name}.tar.gz"
        fi
    done
fi

if [ -n "$VOLUME_FILES" ]; then
    VOLUME_COUNT=0
    for volume_file in $VOLUME_FILES; do
        volume_name=$(basename "$volume_file" .tar.gz)
        echo "   Импорт volume: $volume_name"
        
        # Создаем volume если не существует
        if ! docker volume ls | grep -q "^${volume_name}$"; then
            docker volume create "$volume_name" 2>/dev/null || true
        fi
        
        # Импортируем данные (используем --platform linux/amd64 для избежания проблем с keychain)
        docker run --rm --platform linux/amd64 -v "$volume_name":/data -v "$BACKUP_DIR":/backup alpine \
            sh -c "cd /data && tar xzf /backup/${volume_name}.tar.gz 2>&1" 2>/dev/null || {
            # Альтернативный способ без alpine
            docker run --rm -v "$volume_name":/data busybox sh -c "cd /data && tar xzf /backup/${volume_name}.tar.gz" 2>/dev/null || {
                echo "      ⚠️  Ошибка импорта $volume_name (может быть пустым)"
            }
        }
        
        VOLUME_COUNT=$((VOLUME_COUNT + 1))
        echo "      ✅ Импортирован"
    done
    echo "   ✅ Импортировано volumes: $VOLUME_COUNT"
else
    echo "   ⚠️  Volumes не найдены в бэкапе"
    echo "   💡 Проверьте содержимое: ls -lh $BACKUP_DIR"
fi
echo ""

# 5. Копирование конфигурации
echo "[5/5] Копирование конфигурации..."
if [ -f "$BACKUP_DIR/docker-compose.yml" ]; then
    cp "$BACKUP_DIR/docker-compose.yml" knowledge_os/docker-compose.yml.bak
    echo "   ✅ Конфигурация сохранена как .bak"
fi

if [ -f "$BACKUP_DIR/.env" ]; then
    cp "$BACKUP_DIR/.env" .env.macbook-backup
    echo "   ✅ .env сохранен как .env.macbook-backup"
fi

if [ -f "$BACKUP_DIR/.env.mac-studio" ]; then
    cp "$BACKUP_DIR/.env.mac-studio" .env
    echo "   ✅ .env.mac-studio скопирован как .env"
fi
echo ""

# 5. Запуск контейнеров
echo "=============================================="
echo "✅ ИМПОРТ ЗАВЕРШЕН"
echo "=============================================="
echo ""
echo "🚀 Запуск контейнеров..."
echo ""

# Запуск через setup скрипт
if [ -f "scripts/setup_mac_studio_docker.sh" ]; then
    bash scripts/setup_mac_studio_docker.sh
else
    echo "   Запуск через docker-compose..."
    docker-compose -f knowledge_os/docker-compose.yml up -d
    sleep 10
    docker-compose -f knowledge_os/docker-compose.yml ps
fi

echo ""
echo "✅ МИГРАЦИЯ ЗАВЕРШЕНА!"
echo ""
echo "📋 Проверка сервисов:"
echo "   curl http://localhost:8010/health  # Victoria"
echo "   curl http://localhost:8011/health  # Veronica"
echo "   curl http://localhost:11434/api/tags  # Ollama/MLX"
echo ""
