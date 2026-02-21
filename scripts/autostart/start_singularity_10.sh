#!/bin/bash

# --- ATRA Singularity 14.0 Autostart Script ---
# Этот скрипт запускает всю инфраструктуру микросервисов.

PROJECT_ROOT="/Users/bikos/Documents/atra-web-ide"
cd "$PROJECT_ROOT"

echo "🚀 Запуск Singularity 14.0..."

# 1. Проверка и запуск Docker
if ! docker info > /dev/null 2>&1; then
    echo "🐳 Docker не запущен. Запускаю Docker Desktop..."
    open -a Docker
    
    # Ожидание запуска Docker (макс 2 минуты)
    COUNTER=0
    while ! docker info > /dev/null 2>&1; do
        if [ $COUNTER -gt 24 ]; then
            echo "❌ Ошибка: Docker не запустился вовремя."
            exit 1
        fi
        echo "⏳ Ожидание готовности Docker... ($((COUNTER*5))s)"
        sleep 5
        COUNTER=$((COUNTER+1))
    done
    echo "✅ Docker готов!"
fi

# 2. Создание сети, если её нет
docker network create atra-network 2>/dev/null || true

# 3. Запуск контейнеров Knowledge OS (Core + Redis + Postgres + Worker)
echo "📦 Поднимаем ядро системы (Knowledge OS)..."
docker-compose -f knowledge_os/docker-compose.yml up -d

# 4. Запуск контейнеров Web IDE (Frontend + Backend)
echo "🌐 Поднимаем интерфейс (Web IDE)..."
docker-compose up -d

echo "✅ Все системы запущены!"
echo "👉 Дашборд: http://localhost:8501"
echo "👉 Web IDE: http://localhost:3000"
echo "👉 Victoria API: http://localhost:8010"
echo "👉 Open WebUI (Singularity 15.0): http://localhost:3005"

# Логирование запуска
mkdir -p logs
echo "$(date): System started via autostart script" >> logs/autostart.log
