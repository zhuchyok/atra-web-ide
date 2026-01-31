#!/bin/bash
# Скрипт для запуска всех тестов

set -e

echo "🧪 Запуск тестов Knowledge OS..."
echo ""

# Проверка pytest
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest не установлен"
    echo "💡 Установите: pip install pytest pytest-asyncio"
    exit 1
fi

# Запуск тестов
echo "📋 Запуск unit тестов..."
pytest knowledge_os/tests/test_knowledge_graph.py -v
pytest knowledge_os/tests/test_security.py -v
pytest knowledge_os/tests/test_performance_optimizer.py -v

echo ""
echo "📋 Запуск integration тестов..."
pytest knowledge_os/tests/test_rest_api.py -v

echo ""
echo "📋 Запуск E2E тестов..."
pytest knowledge_os/tests/test_e2e.py -v

echo ""
echo "📋 Запуск нагрузочных тестов..."
pytest knowledge_os/tests/test_load.py -v -m "not slow"

echo ""
echo "✅ Все тесты завершены!"

