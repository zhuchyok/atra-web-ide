#!/bin/bash
# Скрипт запуска полной инфраструктуры ATRA на Mac Studio M4 Max

set -e

echo "🚀 Запуск полной инфраструктуры ATRA на Mac Studio M4 Max"
echo ""

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "   Установите Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Проверка Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен!"
    exit 1
fi

# Проверка Docker daemon
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon не запущен!"
    echo "   Запустите Docker Desktop"
    exit 1
fi

# Создание директорий
echo "📁 Создание директорий..."
mkdir -p logs/mlx logs/knowledge-os logs/agents
mkdir -p backups/knowledge-os
mkdir -p data cache

# Проверка MLX/LLM сервера на хосте (Mac Studio)
echo ""
echo "🔍 Проверка MLX API Server (на хосте) ..."
if curl -s -f "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    echo "✅ MLX API Server доступен на http://localhost:11434"
else
    echo "❌ MLX API Server НЕ доступен на http://localhost:11434"
    echo "   Сначала запустите ваш MLX/LLM сервер на Mac Studio (он у вас уже отдаёт /api/tags)."
    exit 1
fi

# Запуск всех сервисов
echo ""
echo "🐳 Запуск Docker контейнеров..."
docker-compose up -d

# Ожидание готовности БД
echo ""
echo "⏳ Ожидание готовности PostgreSQL..."
sleep 10

# Проверка статуса
echo ""
echo "📊 Статус контейнеров:"
docker-compose ps

echo ""
echo "✅ Инфраструктура запущена!"
echo ""
echo "📋 Доступные сервисы:"
echo "   - MLX API Server (host): http://localhost:11434"
echo "   - Knowledge OS API: http://localhost:8000"
echo "   - Prometheus: http://localhost:9090"
echo "   - Grafana: http://localhost:3000 (admin/atra2025)"
echo ""
echo "🔍 Просмотр логов:"
echo "   docker-compose logs -f [service_name]"
echo ""
echo "📋 Проверка здоровья:"
echo "   curl http://localhost:11434/  # MLX API Server"
echo "   curl http://localhost:8000/   # Knowledge OS API"
