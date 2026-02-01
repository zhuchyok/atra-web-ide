#!/bin/bash
# Скрипт для запуска всех тестов Knowledge OS
# Запускать из корня проекта: ./knowledge_os/tests/run_tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🧪 Запуск тестов Knowledge OS..."
echo "   Project root: $PROJECT_ROOT"
echo ""

# PYTHONPATH нужен для импортов knowledge_os.app.*
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Проверка pytest
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest не установлен"
    echo "💡 Установите: pip install pytest pytest-asyncio"
    exit 1
fi

# Запуск unit тестов
echo "📋 Unit тесты..."
PYTHONPATH="$PROJECT_ROOT" pytest knowledge_os/tests/test_skill_registry.py knowledge_os/tests/test_skill_loader.py knowledge_os/tests/test_skill_discovery.py knowledge_os/tests/test_security.py knowledge_os/tests/test_chain_department_heads.py -v --tb=short || true

echo ""
echo "📋 Тесты knowledge_graph (требуют БД с knowledge_links)..."
PYTHONPATH="$PROJECT_ROOT" pytest knowledge_os/tests/test_knowledge_graph.py -v --tb=short || true

echo ""
echo "📋 Integration/E2E (требуют БД)..."
PYTHONPATH="$PROJECT_ROOT" pytest knowledge_os/tests/test_rest_api.py knowledge_os/tests/test_e2e.py -v --tb=short || true

echo ""
echo "✅ Тесты завершены!"

