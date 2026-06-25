#!/bin/bash
# ============================================================
# 🚀 SINGULARITY 31.2: TOTAL STARTUP (MAC STUDIO)
# ============================================================

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=============================================="
echo "💎 ЗАПУСК SINGULARITY 31.2 НА MAC STUDIO"
echo "=============================================="

# 1. Проверка Docker
if ! docker info &> /dev/null; then
    echo "❌ Docker Desktop не запущен. Пожалуйста, запустите его."
    exit 1
fi

# 2. Проверка сети
if ! docker network ls | grep -q atra-network; then
    docker network create atra-network
    echo "✅ Сеть atra-network создана"
fi

# 3. Запуск всей инфраструктуры (Core + Agents + UI + Monitoring)
# Благодаря 'include' в docker-compose.yml, эта команда поднимет всё
echo "🚀 Запуск всех стеков через Docker Compose..."
docker-compose -f knowledge_os/docker-compose.yml up -d

echo "⏳ Ожидание стабилизации сервисов (15 секунд)..."
sleep 15

# 4. Проверка ключевых узлов
echo "📊 Проверка состояния:"

check_http() {
    if curl -sf --connect-timeout 3 "$2" >/dev/null 2>&1; then
        echo "   ✅ $1: OK"
    else
        echo "   ❌ $1: ОШИБКА"
    fi
}

check_http "Victoria Team Lead" "http://localhost:8010/health"
check_http "Veronica Researcher" "http://localhost:8011/health"
check_http "Knowledge API" "http://localhost:8002/health"
check_http "Open WebUI" "http://localhost:3005/health"
check_http "Dashboard" "http://localhost:8501"

echo "=============================================="
echo "✅ СИСТЕМА ЗАПУЩЕНА И РАБОТАЕТ"
echo "=============================================="
echo "🌐 Ссылки:"
echo "   - Интерфейс: http://localhost:3005"
echo "   - Дашборд:   http://localhost:8501"
echo "   - Графана:   http://localhost:3001"
echo "=============================================="
