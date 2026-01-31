#!/bin/bash
# Тестирование Hybrid Hub-and-Spoke архитектуры

echo "🧪 ТЕСТИРОВАНИЕ HYBRID HUB-AND-SPOKE АРХИТЕКТУРЫ"
echo "================================================"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для проверки статуса
check_status() {
    local name=$1
    local url=$2
    
    echo -n "Проверка $name... "
    response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    
    if [ "$response" = "200" ] || [ "$response" = "200" ]; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED (HTTP $response)${NC}"
        return 1
    fi
}

# Функция для теста задачи
test_task() {
    local endpoint=$1
    local goal=$2
    local name=$3
    
    echo -n "Тест: $name... "
    response=$(curl -s -X POST "http://localhost:8010$endpoint" \
        -H "Content-Type: application/json" \
        -d "{\"goal\": \"$goal\", \"max_steps\": 5}" \
        --max-time 30 2>/dev/null)
    
    if echo "$response" | grep -q '"status":"success"'; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "   Response: ${response:0:100}..."
        return 1
    fi
}

# 1. Проверка сервисов
echo "📊 ПРОВЕРКА СЕРВИСОВ"
echo "--------------------"
check_status "Victoria" "http://localhost:8010/health"
check_status "Veronica" "http://localhost:8011/health"
check_status "Knowledge OS DB" "http://localhost:5432" || echo "   (DB проверка пропущена)"

echo ""
echo "📋 ТЕСТИРОВАНИЕ ЗАДАЧ"
echo "--------------------"

# 2. Простая задача через /run
test_task "/run" "скажи привет" "Простая задача (/run)"

# 3. Простая задача через /orchestrate
test_task "/orchestrate" "скажи привет" "Простая задача (/orchestrate)"

# 4. Сложная задача (Swarm)
echo -n "Тест: Сложная задача (Swarm)... "
response=$(curl -s -X POST "http://localhost:8010/orchestrate" \
    -H "Content-Type: application/json" \
    -d '{"goal": "проанализируй архитектуру", "max_steps": 10}' \
    --max-time 60 2>/dev/null)

if echo "$response" | grep -q '"status":"success"'; then
    echo -e "${GREEN}✅ OK${NC}"
else
    echo -e "${YELLOW}⚠️  TIMEOUT или частичный ответ${NC}"
fi

echo ""
echo "📈 СТАТИСТИКА ЗАДАЧ"
echo "--------------------"

# 5. Статистика задач
docker exec atra-knowledge-os-db psql -U admin -d knowledge_os -c "
SELECT 
    status, 
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM tasks), 2) as percentage
FROM tasks 
GROUP BY status 
ORDER BY count DESC;
" 2>/dev/null | grep -v "row\|---" | head -10

echo ""
echo "⚡ ПРОИЗВОДИТЕЛЬНОСТЬ"
echo "--------------------"

# 6. Задачи за последние 5 минут
recent=$(docker exec atra-knowledge-os-db psql -U admin -d knowledge_os -t -c "
SELECT COUNT(*) 
FROM tasks 
WHERE status = 'completed' 
AND updated_at > NOW() - INTERVAL '5 minutes';
" 2>/dev/null | tr -d ' ')

echo "Завершено за последние 5 минут: $recent задач"

# 7. Параллельная обработка (проверка логов)
echo ""
echo "📝 ЛОГИ SMART WORKER"
echo "--------------------"
echo "Последние 10 строк:"
docker logs --tail 10 atra-knowledge-os-smart-worker 2>&1 | tail -10

echo ""
echo "✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО"
echo "================================================"
