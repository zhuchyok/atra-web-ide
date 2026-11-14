#!/bin/bash
# Проверка всех автономных систем корпорации ATRA
set -u -o pipefail

echo "🔍 ПОЛНАЯ ПРОВЕРКА АВТОНОМНЫХ СИСТЕМ"
echo "================================================"
echo ""

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
ERRORS=0

# Функция проверки
check_system() {
    local name=$1
    local check_cmd=$2

    echo -n "Проверка $name... "
    if eval "$check_cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ АКТИВНА${NC}"
        return 0
    else
        echo -e "${RED}❌ НЕ АКТИВНА${NC}"
        return 1
    fi
}

run_check() {
    if ! check_system "$1" "$2"; then
        ERRORS=$((ERRORS + 1))
    fi
}

# 1. Docker контейнеры
echo "📦 DOCKER КОНТЕЙНЕРЫ:"
run_check "Victoria Agent" "docker ps | grep victoria-agent"
run_check "Veronica Agent" "docker ps | grep veronica-agent"
run_check "Knowledge OS DB" "docker ps | grep knowledge_os_db"
run_check "Smart Worker" "docker ps | grep worker"

# 2. Автономные системы (процессы)
echo ""
echo "🤖 АВТОНОМНЫЕ СИСТЕМЫ (ПРОЦЕССЫ):"
run_check "Enhanced Orchestrator" "ps aux | grep enhanced_orchestrator | grep -v grep"
run_check "Curiosity Engine" "ps aux | grep curiosity_engine | grep -v grep"
run_check "Nightly Learner" "ps aux | grep nightly_learner | grep -v grep"
run_check "Smart Worker" "ps aux | grep smart_worker_autonomous | grep -v grep"

# 3. Активность в БД
echo ""
echo "📊 АКТИВНОСТЬ В БД (последние 24 часа):"
orchestrator_tasks=$(docker exec atra-knowledge-os-db psql -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM tasks WHERE metadata->>'reason' = 'orchestration' AND created_at > NOW() - INTERVAL '24 hours';" 2>/dev/null | tr -d ' ')
curiosity_tasks=$(docker exec atra-knowledge-os-db psql -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM tasks WHERE metadata->>'reason' = 'curiosity_engine_starvation' AND created_at > NOW() - INTERVAL '24 hours';" 2>/dev/null | tr -d ' ')
nightly_tasks=$(docker exec atra-knowledge-os-db psql -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM tasks WHERE metadata->>'reason' = 'nightly_learning' AND created_at > NOW() - INTERVAL '24 hours';" 2>/dev/null | tr -d ' ')
if [ -z "${orchestrator_tasks:-}" ] || [ -z "${curiosity_tasks:-}" ] || [ -z "${nightly_tasks:-}" ]; then
    ERRORS=$((ERRORS + 1))
fi

echo "Enhanced Orchestrator: ${orchestrator_tasks:-0} задач"
echo "Curiosity Engine: ${curiosity_tasks:-0} задач"
echo "Nightly Learner: ${nightly_tasks:-0} задач"

# 4. Последняя активность
echo ""
echo "⏰ ПОСЛЕДНЯЯ АКТИВНОСТЬ:"
last_orch=$(docker exec atra-knowledge-os-db psql -U admin -d knowledge_os -t -c "SELECT MAX(created_at) FROM tasks WHERE metadata->>'reason' = 'orchestration';" 2>/dev/null | tr -d ' ')
last_cur=$(docker exec atra-knowledge-os-db psql -U admin -d knowledge_os -t -c "SELECT MAX(created_at) FROM tasks WHERE metadata->>'reason' = 'curiosity_engine_starvation';" 2>/dev/null | tr -d ' ')

echo "Enhanced Orchestrator: ${last_orch:-неизвестно}"
echo "Curiosity Engine: ${last_cur:-неизвестно}"

# 5. Рекомендации
echo ""
echo "💡 РЕКОМЕНДАЦИИ:"
if [ -z "$orchestrator_tasks" ] || [ "$orchestrator_tasks" = "0" ]; then
    echo -e "${YELLOW}⚠️  Enhanced Orchestrator не активен - нужно запустить${NC}"
fi
if [ -z "$curiosity_tasks" ] || [ "$curiosity_tasks" = "0" ]; then
    echo -e "${YELLOW}⚠️  Curiosity Engine не активен - нужно запустить${NC}"
fi
if [ -z "$nightly_tasks" ] || [ "$nightly_tasks" = "0" ]; then
    echo -e "${YELLOW}⚠️  Nightly Learner не активен - нужно запустить${NC}"
fi

echo ""
echo "✅ ПРОВЕРКА ЗАВЕРШЕНА"
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}❌ Обнаружены проблемы: $ERRORS${NC}"
    exit 1
fi
