#!/bin/bash
# Комплексное тестирование Victoria и Veronica
# Дата: 2026-01-25

set -e

echo "🧪 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ VICTORIA И VERONICA"
echo "================================================"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Счетчики
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Функция для теста
test_check() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    local test_name="$1"
    local command="$2"

    echo "📋 Тест: $test_name"
    if eval "$command" > /tmp/test_output.log 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        cat /tmp/test_output.log | head -5
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# 1. Проверка базовых endpoints
echo "📊 ТЕСТ 1: Базовые endpoints"
echo "-----------------------------------"
test_check "Victoria health" "curl -sf http://localhost:8010/health"
test_check "Veronica health" "curl -sf http://localhost:8011/health"
test_check "Victoria status" "curl -sf http://localhost:8010/status"
test_check "Veronica status" "curl -sf http://localhost:8011/status"
echo ""

# 2. Проверка конфигурации
echo "📊 ТЕСТ 2: Конфигурация"
echo "-----------------------------------"
VICTORIA_STATUS=$(curl -s http://localhost:8010/status)
test_check "Victoria Knowledge OS enabled" "echo '$VICTORIA_STATUS' | python3 -c 'import sys, json; d=json.load(sys.stdin); exit(0 if d.get(\"knowledge_os_enabled\") else 1)'"
test_check "Victoria Cache enabled" "echo '$VICTORIA_STATUS' | python3 -c 'import sys, json; d=json.load(sys.stdin); exit(0 if d.get(\"cache_enabled\") else 1)'"
echo ""

# 3. Простые задачи (кэширование)
echo "🧪 ТЕСТ 3: Простые задачи (кэширование)"
echo "-----------------------------------"
test_check "Victoria простая задача 1" "curl -sf -X POST http://localhost:8010/run -H 'Content-Type: application/json' -d '{\"goal\": \"скажи привет\"}' --max-time 30"
test_check "Victoria простая задача 2 (кэш)" "curl -sf -X POST http://localhost:8010/run -H 'Content-Type: application/json' -d '{\"goal\": \"скажи привет\"}' --max-time 30"
test_check "Veronica простая задача" "curl -sf -X POST http://localhost:8011/run -H 'Content-Type: application/json' -d '{\"goal\": \"покажи файлы\"}' --max-time 30"
echo ""

# 4. Задачи с выбором экспертов
echo "🧪 ТЕСТ 4: Выбор экспертов"
echo "-----------------------------------"
test_check "Victoria backend задача" "curl -sf -X POST http://localhost:8010/run -H 'Content-Type: application/json' -d '{\"goal\": \"создай API endpoint\"}' --max-time 60"
test_check "Victoria ML задача" "curl -sf -X POST http://localhost:8010/run -H 'Content-Type: application/json' -d '{\"goal\": \"настрой обучение модели\"}' --max-time 60"
echo ""

# 5. Сложные задачи (планирование)
echo "🧪 ТЕСТ 5: Сложные задачи (планирование)"
echo "-----------------------------------"
test_check "Victoria сложная задача" "curl -sf -X POST http://localhost:8010/run -H 'Content-Type: application/json' -d '{\"goal\": \"проанализируй код и найди улучшения\"}' --max-time 90"
echo ""

# 6. Проверка Knowledge OS
echo "🔍 ТЕСТ 6: Knowledge OS интеграция"
echo "-----------------------------------"
test_check "Knowledge OS доступность" "docker exec victoria-agent python3 -c 'import asyncio, asyncpg, os; asyncio.run(asyncpg.connect(os.getenv(\"DATABASE_URL\")))'"
echo ""

# 7. Проверка логов
echo "🔍 ТЕСТ 7: Проверка логов"
echo "-----------------------------------"
VICTORIA_ERRORS=$(docker logs victoria-agent --tail 100 2>&1 | grep -iE "(error|exception|traceback|failed)" | wc -l)
VERONICA_ERRORS=$(docker logs veronica-agent --tail 100 2>&1 | grep -iE "(error|exception|traceback|failed)" | wc -l)

if [ "$VICTORIA_ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✅ Victoria: ошибок не найдено${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠️  Victoria: найдено $VICTORIA_ERRORS ошибок${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))

if [ "$VERONICA_ERRORS" -eq 0 ]; then
    echo -e "${GREEN}✅ Veronica: ошибок не найдено${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠️  Veronica: найдено $VERONICA_ERRORS ошибок${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi
TESTS_TOTAL=$((TESTS_TOTAL + 1))
echo ""

# Итоги
echo "================================================"
echo "📊 ИТОГИ ТЕСТИРОВАНИЯ"
echo "================================================"
echo "Всего тестов: $TESTS_TOTAL"
echo -e "${GREEN}Пройдено: $TESTS_PASSED${NC}"
echo -e "${RED}Провалено: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!${NC}"
    exit 0
else
    echo -e "${RED}❌ Некоторые тесты провалены${NC}"
    exit 1
fi
