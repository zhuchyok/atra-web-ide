#!/bin/bash
# ============================================================
# ЗАПУСТИТЬ ЭТОТ СКРИПТ НА MAC STUDIO
# Скопируйте и выполните на Mac Studio в терминале
# ============================================================

cd ~/Documents/atra-web-ide

# Настройка PATH для Docker
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

echo "=============================================="
echo "🚀 ЗАПУСК ВСЕХ КОНТЕЙНЕРОВ НА MAC STUDIO"
echo "=============================================="
echo ""

# Проверка Docker
echo "[1/3] Проверка Docker..."
if ! docker info &> /dev/null; then
    echo "   ❌ Docker не запущен!"
    echo "   💡 Запустите Docker Desktop"
    exit 1
fi
echo "   ✅ Docker готов"
echo ""

# Создание сети
echo "[2/3] Проверка сети..."
if ! docker network ls | grep -q atra-network; then
    docker network create atra-network
    echo "   ✅ Сеть создана"
else
    echo "   ✅ Сеть уже существует"
fi
echo ""

# Запуск контейнеров
echo "[3/3] Запуск контейнеров..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    docker-compose -f knowledge_os/docker-compose.yml up -d 2>&1 | grep -v "level=warning" || true
    echo ""
    echo "   ⏳ Ожидание запуска (20 секунд)..."
    sleep 20
    echo ""
    echo "   📊 Статус контейнеров:"
    docker-compose -f knowledge_os/docker-compose.yml ps 2>&1 | grep -v "level=warning" || true
else
    echo "   ❌ docker-compose.yml не найден!"
    exit 1
fi

echo ""
echo "=============================================="
echo "✅ ПРОВЕРКА СЕРВИСОВ"
echo "=============================================="
echo ""

check_service() {
    local name=$1
    local url=$2
    if curl -s -f --connect-timeout 3 "$url" >/dev/null 2>&1; then
        echo "   ✅ $name: работает"
    else
        echo "   ⚠️  $name: не отвечает (может еще запускаться)"
    fi
}

check_service "Victoria (8010)" "http://localhost:8010/health"
check_service "Veronica (8011)" "http://localhost:8011/health"
check_service "Ollama/MLX (11434)" "http://localhost:11434/api/tags"
check_service "Knowledge OS (8000)" "http://localhost:8000/health"

echo ""
echo "=============================================="
echo "✅ ГОТОВО!"
echo "=============================================="
echo ""
echo "🌐 Доступные сервисы:"
echo "   - Victoria: http://localhost:8010"
echo "   - Veronica: http://localhost:8011"
echo "   - Ollama/MLX: http://localhost:11434"
echo "   - Knowledge OS: http://localhost:8000"
echo ""
