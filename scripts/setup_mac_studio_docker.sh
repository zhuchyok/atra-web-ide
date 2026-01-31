#!/bin/bash
# Настройка и запуск Docker на Mac Studio
# Запускать на Mac Studio: bash scripts/setup_mac_studio_docker.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🐳 НАСТРОЙКА DOCKER НА MAC STUDIO"
echo "=============================================="
echo ""

# 1. Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "   Установите Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon не запущен!"
    echo "   Запустите Docker Desktop"
    exit 1
fi

echo "✅ Docker установлен и запущен"
echo ""

# 2. Создание сети если нужно
echo "[1/4] Проверка Docker сети..."
if ! docker network ls | grep -q atra-network; then
    echo "   Создание сети atra-network..."
    docker network create atra-network
    echo "   ✅ Сеть создана"
else
    echo "   ✅ Сеть atra-network уже существует"
fi
echo ""

# 3. Проверка MLX/Ollama на хосте
echo "[2/4] Проверка MLX/Ollama API Server..."
if curl -s -f "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    echo "   ✅ MLX/Ollama API Server доступен на http://localhost:11434"
    MODELS_COUNT=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('models', [])))" 2>/dev/null || echo "0")
    echo "   📊 Доступно моделей: $MODELS_COUNT"
else
    echo "   ⚠️  MLX/Ollama API Server НЕ доступен на http://localhost:11434"
    echo "   💡 Запустите MLX API Server:"
    echo "      bash scripts/start_mlx_api_server.sh"
    echo "   Или установите Ollama:"
    echo "      brew install ollama && ollama serve"
fi
echo ""

# 4. Запуск Docker контейнеров
echo "[3/4] Запуск Docker контейнеров..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    echo "   Запуск через docker-compose..."
    docker-compose -f knowledge_os/docker-compose.yml up -d
    
    echo "   ⏳ Ожидание готовности сервисов (15 секунд)..."
    sleep 15
    
    echo "   📊 Статус контейнеров:"
    docker-compose -f knowledge_os/docker-compose.yml ps
    
    echo "   ✅ Контейнеры запущены"
else
    echo "   ❌ docker-compose.yml не найден!"
    exit 1
fi
echo ""

# 5. Проверка статуса
echo "[4/4] Проверка статуса сервисов..."
echo ""

check_service() {
    local name=$1
    local url=$2
    if curl -s -f --connect-timeout 3 "$url" >/dev/null 2>&1; then
        echo "   ✅ $name: доступен"
        return 0
    else
        echo "   ❌ $name: недоступен"
        return 1
    fi
}

check_service "Victoria (8010)" "http://localhost:8010/health"
check_service "Veronica (8011)" "http://localhost:8011/health"
check_service "Victoria MCP (8012)" "http://localhost:8012/sse"
check_service "Ollama/MLX (11434)" "http://localhost:11434/api/tags"
check_service "Knowledge OS (8000)" "http://localhost:8000/health"

echo ""
echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "📋 Доступные сервисы:"
echo "   - Victoria: http://localhost:8010"
echo "   - Veronica: http://localhost:8011"
echo "   - Victoria MCP: http://localhost:8012/sse"
echo "   - Ollama/MLX: http://localhost:11434"
echo "   - Knowledge OS: http://localhost:8000"
echo ""
echo "🌐 Для удаленного доступа:"
echo "   - Victoria: http://192.168.1.64:8010"
echo "   - Veronica: http://192.168.1.64:8011"
echo "   - Ollama/MLX: http://192.168.1.64:11434"
echo ""
echo "📊 Проверка статуса:"
echo "   docker-compose -f knowledge_os/docker-compose.yml ps"
echo ""
