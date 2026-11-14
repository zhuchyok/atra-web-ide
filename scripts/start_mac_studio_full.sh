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

# Проверка Ollama brain на хосте (Mac Studio). MLX fallback — :11435.
echo ""
echo "🔍 Проверка Ollama brain (на хосте) ..."
if curl -s -f "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    echo "✅ Ollama brain доступен на http://localhost:11434"
else
    echo "❌ Ollama brain НЕ доступен на http://localhost:11434"
    echo "   Сначала запустите Ollama на Mac Studio (он отдаёт /api/tags)."
    exit 1
fi
if curl -s -f "http://localhost:11435/" >/dev/null 2>&1; then
    echo "✅ MLX fallback доступен на http://localhost:11435"
else
    echo "⚠️  MLX fallback :11435 недоступен (optional)"
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

SETUP_FAIL=0
for url in \
  "http://localhost:8010/health" \
  "http://localhost:8080/health" \
  "http://localhost:8002/health"
do
  if ! curl -sf --connect-timeout 5 "$url" >/dev/null; then
    echo "❌ Health fail: $url"
    SETUP_FAIL=1
  fi
done

echo ""
if [ "$SETUP_FAIL" -eq 0 ]; then
  echo "✅ Инфраструктура запущена!"
else
  echo "⚠️ Инфраструктура поднята с ошибками health"
fi
echo ""
echo "📋 Доступные сервисы:"
echo "   - Ollama brain (host): http://localhost:11434"
echo "   - MLX fallback (host): http://localhost:11435"
echo "   - Knowledge OS REST: http://localhost:8002"
echo "   - Victoria: http://localhost:8010"
echo "   - Prometheus: http://localhost:9091"
echo "   - Grafana: http://localhost:3002"
echo "   - Frontend: http://localhost:3000"
echo ""
echo "🔍 Просмотр логов:"
echo "   docker-compose logs -f [service_name]"
echo ""
echo "📋 Проверка здоровья:"
echo "   curl http://localhost:11434/api/tags  # Ollama"
echo "   curl http://localhost:8002/health     # Knowledge OS REST"
exit "$SETUP_FAIL"
