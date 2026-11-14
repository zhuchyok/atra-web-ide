#!/bin/bash
# Скрипт проверки всех сервисов
set -euo pipefail

ERRORS=0

echo "🔍 Проверка всех сервисов Mac Studio M4 Max"
echo ""

# Проверка Docker контейнеров
echo "📊 Статус Docker контейнеров:"
docker-compose ps

echo ""
echo "🏥 Health Checks:"
echo ""

# MLX API Server
MLX_PORT=${MLX_API_PORT:-11435}
echo -n "   MLX API Server (${MLX_PORT}): "
if curl -s -f http://localhost:${MLX_PORT}/ > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
    ERRORS=$((ERRORS + 1))
fi

# Knowledge OS REST (host publish is 8002)
echo -n "   Knowledge OS REST (8002): "
if curl -s -f http://localhost:8002/health > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
    ERRORS=$((ERRORS + 1))
fi

# Victoria / Veronica
echo -n "   Victoria Agent (8010): "
if curl -s -f http://localhost:8010/health > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
    ERRORS=$((ERRORS + 1))
fi
echo -n "   Veronica Agent (8011): "
if curl -s -f http://localhost:8011/health > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
    ERRORS=$((ERRORS + 1))
fi

# Prometheus (live host 9091)
echo -n "   Prometheus (9091): "
if curl -s -f http://localhost:9091/-/healthy > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
    ERRORS=$((ERRORS + 1))
fi

# Grafana (live host 3002; :3000 is frontend)
echo -n "   Grafana (3002): "
if curl -s -f http://localhost:3002/api/health > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
    ERRORS=$((ERRORS + 1))
fi

echo ""
echo "📋 Логи последних 10 строк от каждого сервиса:"
echo ""

for service in mlx-api-server knowledge-os-api victoria-agent veronica-agent; do
    echo "--- $service ---"
    docker-compose logs --tail=10 $service 2>/dev/null || echo "  (нет логов)"
    echo ""
done

if [ "$ERRORS" -gt 0 ]; then
    echo "❌ Найдено проблем: $ERRORS"
    exit 1
fi
