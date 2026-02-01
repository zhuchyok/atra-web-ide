#!/bin/bash
# Верификация самовосстановления Mac Studio после перезагрузки
# Запускать после перезагрузки или для проверки готовности системы
# Мировые практики: 12-Factor App disposability, Docker restart policies, health checks

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🔍 ВЕРИФИКАЦИЯ САМОВОССТАНОВЛЕНИЯ MAC STUDIO"
echo "=============================================="
echo ""

OK=0
TOTAL=0
WARN=0

check() {
    local name="$1"
    local cmd="$2"
    local fix="$3"
    TOTAL=$((TOTAL + 1))
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  ✅ $name"
        OK=$((OK + 1))
        return 0
    else
        echo "  ❌ $name"
        [ -n "$fix" ] && echo "     💡 $fix"
        return 1
    fi
}

warn() {
    local name="$1"
    local cmd="$2"
    TOTAL=$((TOTAL + 1))
    if eval "$cmd" >/dev/null 2>&1; then
        echo "  ✅ $name"
        OK=$((OK + 1))
        return 0
    else
        echo "  ⚠️  $name (не критично)"
        WARN=$((WARN + 1))
        return 1
    fi
}

echo "1️⃣  Базовая инфраструктура"
echo "-------------------------------------------"
check "Docker запущен" "docker info" "Запустите Docker Desktop" || true
check "Сеть atra-network" "docker network inspect atra-network >/dev/null 2>&1" "bash scripts/start_all_on_mac_studio.sh" || true
echo ""

echo "2️⃣  Knowledge OS (PostgreSQL, Redis, агенты)"
echo "-------------------------------------------"
check "PostgreSQL (knowledge_postgres)" "docker exec knowledge_postgres pg_isready -U admin -d knowledge_os 2>/dev/null" "docker-compose -f knowledge_os/docker-compose.yml up -d db" || true
check "Redis (knowledge_redis)" "docker exec knowledge_redis redis-cli ping 2>/dev/null | grep -q PONG" "docker-compose -f knowledge_os/docker-compose.yml up -d redis" || true
check "Victoria Agent (8010)" "curl -sf --connect-timeout 5 http://localhost:8010/health >/dev/null" "docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent" || true
check "Veronica Agent (8011)" "curl -sf --connect-timeout 5 http://localhost:8011/health >/dev/null" "docker-compose -f knowledge_os/docker-compose.yml up -d veronica-agent" || true
check "Knowledge OS Worker" "docker ps --format '{{.Names}}' | grep -q knowledge_os_worker" "docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_os_worker" || true
check "Nightly Learner" "docker ps --format '{{.Names}}' | grep -q knowledge_nightly" "docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_nightly" || true
check "Knowledge Orchestrator" "docker ps --format '{{.Names}}' | grep -q knowledge_os_orchestrator" "docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_os_orchestrator" || true
warn "Knowledge REST API (8002)" "curl -sf --connect-timeout 5 http://localhost:8002/health >/dev/null || curl -sf --connect-timeout 5 http://localhost:8002/ >/dev/null" || true
echo ""

echo "3️⃣  LLM и модели"
echo "-------------------------------------------"
check "Ollama (11434)" "curl -sf --connect-timeout 5 http://localhost:11434/api/tags >/dev/null" "brew services start ollama" || true
warn "MLX API Server (11435)" "curl -sf --connect-timeout 5 http://localhost:11435/api/tags >/dev/null" || true
echo ""

echo "4️⃣  ATRA Web IDE"
echo "-------------------------------------------"
check "Backend (8080)" "curl -sf --connect-timeout 5 http://localhost:8080/health >/dev/null" "docker-compose up -d backend" || true
warn "Frontend (3000)" "curl -sf --connect-timeout 5 http://localhost:3000 >/dev/null" || true
warn "Victoria Telegram Bot" "pgrep -f victoria_telegram_bot >/dev/null" "cd $ROOT && python3 -m src.agents.bridge.victoria_telegram_bot &" || true
echo ""

echo "5️⃣  Мониторинг и дашборды"
echo "-------------------------------------------"
warn "Victoria MCP (8012)" "curl -sf --connect-timeout 5 http://localhost:8012/sse >/dev/null" || true
warn "Prometheus (9092)" "curl -sf --connect-timeout 5 http://localhost:9092/-/healthy >/dev/null" || true
warn "Grafana (3001)" "curl -sf --connect-timeout 5 http://localhost:3001/api/health >/dev/null" || true
warn "Corporation Dashboard (8501)" "curl -sf --connect-timeout 5 http://localhost:8501 >/dev/null" || true
echo ""

echo "6️⃣  Launchd (автозапуск при перезагрузке)"
echo "-------------------------------------------"
warn "Система самовосстановления" "launchctl list 2>/dev/null | grep -q com.atra.auto-recovery" || true
warn "MLX Monitor" "launchctl list 2>/dev/null | grep -q com.atra.mlx-monitor" || true
warn "Victoria MCP (launchd)" "launchctl list 2>/dev/null | grep -q com.atra.victoria-mcp" || true
warn "Docker StartAtLogin" "defaults read com.docker.docker StartAtLogin 2>/dev/null | grep -q 1" || true
warn "Ollama (brew services)" "brew services list 2>/dev/null | grep ollama | grep -q started" || true
echo ""

echo "=============================================="
echo "📊 ИТОГ: $OK/$TOTAL критичных, $WARN некритичных"
echo "=============================================="
echo ""

if [ "$OK" -lt 7 ]; then
    echo "⚠️  Критичные сервисы недоступны. Запустите:"
    echo "   bash scripts/start_all_on_mac_studio.sh"
    echo "   bash scripts/system_auto_recovery.sh"
    echo ""
    echo "📋 Полная настройка автозапуска (один раз):"
    echo "   bash scripts/setup_complete_autostart.sh"
    echo "   bash scripts/setup_system_auto_recovery.sh"
    exit 1
fi

echo "✅ Система готова к работе после перезагрузки Mac Studio"
echo ""
echo "📝 Проверка после перезагрузки: bash scripts/verify_mac_studio_self_recovery.sh"
exit 0
