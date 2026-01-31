#!/bin/bash
# Быстрый перезапуск Victoria с проверкой

cd "$(dirname "$0")"

echo "🔄 Перезапуск Victoria..."
echo ""

# Перезапуск
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent

echo ""
echo "⏳ Ожидание запуска (5 секунд)..."
sleep 5

echo ""
echo "📊 Проверка статуса:"
docker ps --filter "name=victoria-agent" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🔍 Проверка подключения к БД:"
docker logs victoria-agent 2>&1 | tail -30 | grep -i "database\|DATABASE_URL\|эксперты\|fallback\|🔌" || echo "   Проверяю все логи..."

echo ""
echo "📋 Health check:"
curl -s http://localhost:8010/health 2>/dev/null | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8010/health 2>/dev/null || echo "   Victoria еще запускается..."

echo ""
echo "✅ Готово!"
