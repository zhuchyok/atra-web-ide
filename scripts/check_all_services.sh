#!/bin/bash
# Скрипт проверки всех сервисов

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
fi

# Knowledge OS API
echo -n "   Knowledge OS API: "
if curl -s -f http://localhost:8000/ > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
fi

# Prometheus
echo -n "   Prometheus: "
if curl -s -f http://localhost:9090/-/healthy > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
fi

# Grafana
echo -n "   Grafana: "
if curl -s -f http://localhost:3000/api/health > /dev/null; then
    echo "✅ Онлайн"
else
    echo "❌ Офлайн"
fi

echo ""
echo "📋 Логи последних 10 строк от каждого сервиса:"
echo ""

for service in mlx-api-server knowledge-os-api victoria-agent veronica-agent; do
    echo "--- $service ---"
    docker-compose logs --tail=10 $service 2>/dev/null || echo "  (нет логов)"
    echo ""
done
