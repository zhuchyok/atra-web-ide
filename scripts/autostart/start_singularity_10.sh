#!/bin/bash

# --- ATRA Singularity 31.2 Autostart Script ---
# Этот скрипт запускает всю инфраструктуру микросервисов Роя.

PROJECT_ROOT="/Users/bikos/Documents/atra-web-ide"
cd "$PROJECT_ROOT"

echo "🚀 Запуск Singularity 31.2 (Total Crystallization)..."

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

# 3. Запуск Knowledge OS (Core + Agents + UI + Monitoring)
# Используем include в основном файле для автоматического подтягивания всех стеков
echo "📦 Поднимаем ядро и агентов (Knowledge OS 31.2)..."
docker-compose -f knowledge_os/docker-compose.yml up -d

# 4. Запуск Web IDE (Frontend + Backend + Gateway)
echo "🌐 Поднимаем интерфейс и шлюз (Web IDE)..."
docker-compose up -d

# 5. Запуск Rust Gateway (если собран)
if [ -f "$PROJECT_ROOT/target/release/gateway" ]; then
    echo "🦀 Запуск Rust Gateway..."
    ps aux | grep gateway | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
    RUST_LOG=info WORKSPACE_ROOT="$PROJECT_ROOT" "$PROJECT_ROOT/target/release/gateway" > "$PROJECT_ROOT/logs/gateway_autostart.log" 2>&1 &
fi

echo "✅ Все системы Singularity 31.2 запущены!"
echo "👉 Интерфейс: http://localhost:3005 (Open WebUI) / http://localhost:3000 (Web IDE)"
echo "👉 Дашборд:   http://localhost:8501"
echo "👉 Мониторинг: http://localhost:3001 (Grafana)"

# Логирование запуска
mkdir -p logs
echo "$(date): Singularity 31.2 started via autostart script" >> logs/autostart.log
