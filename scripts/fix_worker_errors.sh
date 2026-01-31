#!/bin/bash
# Исправление ошибок worker для автоматической работы

set -e

echo "🔧 Исправление ошибок worker..."
echo ""

# Проверяем ошибки в логах
echo "📋 Проверка ошибок worker..."
ERRORS=$(docker logs knowledge_os_worker --tail 50 2>&1 | grep -i "error\|failed\|exception" | head -5)

if [ -n "$ERRORS" ]; then
    echo "⚠️  Найдены ошибки:"
    echo "$ERRORS"
    echo ""
    echo "🔍 Анализ ошибок..."
    
    # Проверяем подключение к БД
    if docker logs knowledge_os_worker 2>&1 | grep -q "Name or service not known"; then
        echo "   ❌ Проблема: Неправильное имя хоста БД"
        echo "   ✅ Решение: Использовать knowledge_postgres вместо localhost"
    fi
    
    # Проверяем Redis
    if docker logs knowledge_os_worker 2>&1 | grep -q "redis"; then
        echo "   ❌ Проблема: Redis недоступен"
        echo "   ✅ Решение: Использовать knowledge_redis:6379"
    fi
else
    echo "   ✅ Ошибок не найдено"
fi

echo ""
echo "✅ Проверка завершена"
