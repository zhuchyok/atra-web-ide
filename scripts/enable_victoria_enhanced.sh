#!/bin/bash
# Скрипт включения Victoria Enhanced режима
# Запуск: bash scripts/enable_victoria_enhanced.sh

set -e

echo "🚀 Включение Victoria Enhanced режима..."
echo ""

# Проверяем что мы в корне проекта
if [ ! -f "PLAN.md" ]; then
    echo "❌ Запустите скрипт из корня проекта"
    exit 1
fi

# 1. Обновляем docker-compose.yml (уже сделано в коде)
echo "✅ docker-compose.yml обновлен с USE_VICTORIA_ENHANCED=true"

# 2. Перезапускаем Victoria
echo ""
echo "🔄 Перезапуск Victoria с Enhanced режимом..."

if docker ps | grep -q victoria-agent; then
    echo "   Останавливаем текущий контейнер..."
    docker-compose -f knowledge_os/docker-compose.yml stop victoria-agent
    docker-compose -f knowledge_os/docker-compose.yml rm -f victoria-agent
fi

echo "   Запускаем Victoria Enhanced..."
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent

# 3. Ждем запуска
sleep 3

# 4. Проверяем работу
echo ""
echo "🔍 Проверка работы Victoria Enhanced..."

if curl -s http://localhost:8010/health > /dev/null 2>&1; then
    echo "✅ Victoria работает на http://localhost:8010"
    
    # Проверяем что Enhanced режим активен
    echo ""
    echo "📊 Тестируем Enhanced режим..."
    response=$(curl -s -X POST http://localhost:8010/run \
        -H "Content-Type: application/json" \
        -d '{"goal": "Тест Victoria Enhanced"}')
    
    if echo "$response" | grep -q "method"; then
        echo "✅ Victoria Enhanced активен!"
        echo "   Ответ содержит информацию о методе"
    else
        echo "⚠️  Victoria Enhanced может быть не активен"
        echo "   Проверьте логи: docker logs victoria-agent"
    fi
else
    echo "❌ Victoria не отвечает"
    echo "   Проверьте логи: docker logs victoria-agent"
    exit 1
fi

echo ""
echo "✅ Victoria Enhanced включен и работает!"
echo ""
echo "📝 Использование:"
echo "   curl -X POST http://localhost:8010/run \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"goal\": \"Ваша задача\"}'"
echo ""
echo "📊 Проверка статуса:"
echo "   curl http://localhost:8010/status"
echo ""
