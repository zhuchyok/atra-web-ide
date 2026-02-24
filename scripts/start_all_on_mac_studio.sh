#!/bin/bash
# Полный запуск всех сервисов на Mac Studio
# Запускать на Mac Studio: bash scripts/start_all_on_mac_studio.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚀 ПОЛНЫЙ ЗАПУСК ВСЕХ СЕРВИСОВ НА MAC STUDIO"
echo "=============================================="
echo ""

# 1. Проверка Docker
echo "[1/6] Проверка Docker..."
if ! command -v docker &> /dev/null; then
    echo "   ❌ Docker не установлен!"
    echo "   Установите Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "   ❌ Docker daemon не запущен!"
    echo "   Запустите Docker Desktop"
    exit 1
fi
echo "   ✅ Docker готов"
echo ""

# 2. Создание сети
echo "[2/6] Создание Docker сети..."
if ! docker network ls | grep -q atra-network; then
    docker network create atra-network
    echo "   ✅ Сеть atra-network создана"
else
    echo "   ✅ Сеть atra-network уже существует"
fi
echo ""

# 3. Проверка MLX/Ollama
echo "[3/6] Проверка MLX/Ollama API Server..."
if curl -s -f "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    MODELS_COUNT=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('models', [])))" 2>/dev/null || echo "0")
    echo "   ✅ MLX/Ollama доступен (моделей: $MODELS_COUNT)"
else
    echo "   ⚠️  MLX/Ollama НЕ доступен на http://localhost:11434"
    echo "   💡 Запустите: bash scripts/start_mlx_api_server.sh"
    echo "   Или: brew install ollama && ollama serve"
    read -p "   Продолжить без MLX/Ollama? (y/n): " continue_without
    if [ "$continue_without" != "y" ]; then
        exit 1
    fi
fi
echo ""

# 4. Импорт данных с MacBook (если есть)
echo "[4/6] Проверка миграции с MacBook..."
BACKUP_DIR=$(ls -td backups/migration/atra-docker-migration-* 2>/dev/null | head -1)
if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
    echo "   📦 Найден бэкап с MacBook: $BACKUP_DIR"
    echo "   💡 Бэкап содержит:"
    echo "      - Docker volumes"
    echo "      - Docker образы"
    echo "      - Конфигурация"
    echo ""
    read -p "   Импортировать данные с MacBook? (y/n): " import_data
    if [ "$import_data" = "y" ]; then
        if [ -f "scripts/import_docker_from_macbook.sh" ]; then
            echo "   🚀 Импорт данных..."
            bash scripts/import_docker_from_macbook.sh
            if [ $? -eq 0 ]; then
                echo "   ✅ Импорт завершен успешно"
            else
                echo "   ⚠️  Ошибка импорта, продолжаем без импорта"
            fi
        else
            echo "   ⚠️  Скрипт импорта не найден"
        fi
    else
        echo "   ℹ️  Импорт пропущен"
    fi
else
    echo "   ℹ️  Бэкап с MacBook не найден (это нормально, если миграция не нужна)"
    echo "   💡 Для миграции выполните на MacBook:"
    echo "      bash scripts/full_migration_macbook_to_macstudio.sh"
fi
echo ""

# 5. Запуск контейнеров
echo "[5/6] Запуск Docker контейнеров..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    echo "   Запуск через docker-compose..."
    docker-compose -f knowledge_os/docker-compose.yml up -d

    echo "   ⏳ Ожидание готовности сервисов (20 секунд)..."
    sleep 20

    echo "   📊 Статус контейнеров:"
    docker-compose -f knowledge_os/docker-compose.yml ps
    echo "   ✅ Контейнеры запущены"
else
    echo "   ❌ docker-compose.yml не найден!"
    exit 1
fi
echo ""

# 6. Проверка сервисов
echo "[6/6] Проверка доступности сервисов..."
echo ""

check_service() {
    local name=$1
    local url=$2
    if curl -s -f --connect-timeout 5 "$url" >/dev/null 2>&1; then
        echo "   ✅ $name: доступен"
        return 0
    else
        echo "   ❌ $name: недоступен"
        return 1
    fi
}

SERVICES_OK=0
check_service "Victoria (8010)" "http://localhost:8010/health" && SERVICES_OK=$((SERVICES_OK + 1))
check_service "Veronica (8011)" "http://localhost:8011/health" && SERVICES_OK=$((SERVICES_OK + 1))
check_service "Victoria MCP (8012)" "http://localhost:8012/sse" && SERVICES_OK=$((SERVICES_OK + 1))
check_service "Ollama/MLX (11434)" "http://localhost:11434/api/tags" && SERVICES_OK=$((SERVICES_OK + 1))
check_service "Knowledge OS (8000)" "http://localhost:8000/health" && SERVICES_OK=$((SERVICES_OK + 1))

echo ""
echo "=============================================="
if [ $SERVICES_OK -eq 5 ]; then
    echo "✅ ВСЕ СЕРВИСЫ ЗАПУЩЕНЫ И РАБОТАЮТ!"
else
    echo "⚠️  НЕКОТОРЫЕ СЕРВИСЫ НЕДОСТУПНЫ ($SERVICES_OK/5)"
fi
echo "=============================================="
echo ""
echo "📋 Доступные сервисы:"
echo "   - Victoria: http://localhost:8010"
echo "   - Veronica: http://localhost:8011"
echo "   - Victoria MCP: http://localhost:8012/sse"
echo "   - Ollama/MLX: http://localhost:11434"
echo "   - Knowledge OS: http://localhost:8000"
echo ""
echo "🌐 Доступ с MacBook:"
echo "   - Victoria: http://192.168.1.64:8010"
echo "   - Veronica: http://192.168.1.64:8011"
echo "   - Ollama/MLX: http://192.168.1.64:11434"
echo ""
echo "🌍 Доступ из интернета (через SSH туннель):"
echo "   - Victoria: http://185.177.216.15:8010"
echo "   - Veronica: http://185.177.216.15:8011"
echo "   - Ollama/MLX: http://185.177.216.15:11434"
echo ""
echo "📊 Просмотр логов:"
echo "   docker-compose -f knowledge_os/docker-compose.yml logs -f [service_name]"
echo ""
