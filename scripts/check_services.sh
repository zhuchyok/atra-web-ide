#!/bin/bash
# ============================================================================
# Проверка всех сервисов ATRA
# ============================================================================

echo "🔍 ATRA Services Check"
echo "======================"
echo ""

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_service() {
    local name="$1"
    local url="$2"
    local timeout="${3:-3}"
    
    if curl -s --connect-timeout $timeout "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC} $name: $url"
        return 0
    else
        echo -e "${RED}❌${NC} $name: $url"
        return 1
    fi
}

echo "📡 Локальные сервисы:"
check_service "Ollama (local)" "http://localhost:11434/api/tags"
check_service "Victoria Agent" "http://localhost:8010/health"
check_service "Veronica Agent" "http://localhost:8011/health"
check_service "Victoria MCP" "http://localhost:8012/sse"
check_service "Knowledge OS API" "http://localhost:8000/health"
check_service "VectorCore" "http://localhost:8001/health"

echo ""
echo "🖥️  Mac Studio (192.168.1.64):"
check_service "Ollama (Mac Studio)" "http://192.168.1.64:11434/api/tags"
check_service "Victoria (Mac Studio)" "http://192.168.1.64:8010/health"
check_service "Veronica (Mac Studio)" "http://192.168.1.64:8011/health"

echo ""
echo "🌐 Серверы корпорации:"
check_service "Server 1 (185.177.216.15)" "http://185.177.216.15:11434/api/tags" 5
check_service "Server 2 (46.149.66.170)" "http://46.149.66.170:8000/health" 5

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
