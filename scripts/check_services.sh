#!/bin/bash
# ============================================================================
# Проверка всех сервисов ATRA
# ============================================================================
set -u -o pipefail

echo "🔍 ATRA Services Check"
echo "======================"
echo ""

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
FAILURES=0
STRICT_CHECK_SERVICES="${STRICT_CHECK_SERVICES:-true}"

check_service() {
    local name="$1"
    local url="$2"
    local timeout="${3:-3}"

    if curl -fsS --connect-timeout $timeout "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC} $name: $url"
        return 0
    else
        echo -e "${RED}❌${NC} $name: $url"
        return 1
    fi
}

echo "📡 Локальные сервисы:"
check_service "Ollama (local)" "http://localhost:11434/api/tags" || FAILURES=$((FAILURES + 1))
check_service "Ollama Coder (11436)" "http://localhost:11436/api/tags" || FAILURES=$((FAILURES + 1))
check_service "Ollama Hands (11437)" "http://localhost:11437/api/tags" || FAILURES=$((FAILURES + 1))
check_service "Victoria Agent" "http://localhost:8010/health" || FAILURES=$((FAILURES + 1))
check_service "Veronica Agent" "http://localhost:8011/health" || FAILURES=$((FAILURES + 1))
if [ "${CHECK_LEGACY_MCP:-false}" = "true" ]; then
    check_service "Victoria MCP" "http://localhost:8012/sse" || FAILURES=$((FAILURES + 1))
fi
check_service "Knowledge OS REST" "http://localhost:8002/health" || FAILURES=$((FAILURES + 1))
check_service "VectorCore" "http://localhost:8001/health" || FAILURES=$((FAILURES + 1))

echo ""
echo "🖥️  Mac Studio (192.168.1.64):"
check_service "Ollama (Mac Studio)" "http://192.168.1.64:11434/api/tags" || FAILURES=$((FAILURES + 1))
check_service "Victoria (Mac Studio)" "http://192.168.1.64:8010/health" || FAILURES=$((FAILURES + 1))
check_service "Veronica (Mac Studio)" "http://192.168.1.64:8011/health" || FAILURES=$((FAILURES + 1))

echo ""
echo "🌐 Серверы корпорации:"
check_service "Server 1 (185.177.216.15)" "http://185.177.216.15:11434/api/tags" 5 || FAILURES=$((FAILURES + 1))
check_service "Server 2 (46.149.66.170)" "http://46.149.66.170:8000/health" 5 || FAILURES=$((FAILURES + 1))

echo ""
echo "📊 Docker контейнеры:"
if command -v docker &> /dev/null; then
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker не запущен"
else
    echo "Docker не установлен"
fi

echo ""
echo "🔧 Ollama модели (если доступен):"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    curl -s http://localhost:11434/api/tags | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    if models:
        for m in models[:10]:
            size = m.get('size', 0) / 1e9
            print(f\"  - {m['name']} ({size:.1f}GB)\")
    else:
        print('  Нет моделей')
except:
    print('  Ошибка чтения')
" 2>/dev/null
elif curl -s http://192.168.1.64:11434/api/tags > /dev/null 2>&1; then
    echo "  (с Mac Studio)"
    curl -s http://192.168.1.64:11434/api/tags | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    models = data.get('models', [])
    if models:
        for m in models[:10]:
            size = m.get('size', 0) / 1e9
            print(f\"  - {m['name']} ({size:.1f}GB)\")
    else:
        print('  Нет моделей')
except:
    print('  Ошибка чтения')
" 2>/dev/null
else
    echo "  Ollama недоступен"
fi

echo ""
echo "Итог: FAILURES=$FAILURES (STRICT_CHECK_SERVICES=$STRICT_CHECK_SERVICES)"
if [ "$FAILURES" -gt 0 ] && [ "$STRICT_CHECK_SERVICES" = "true" ]; then
    exit 1
fi
exit 0
