#!/bin/bash
# Проверка и запуск всех контейнеров на Mac Studio
# Запускать на Mac Studio: bash scripts/check_and_start_containers.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Настройка PATH для Docker Desktop на Mac
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

echo "=============================================="
echo "🔍 ПРОВЕРКА И ЗАПУСК КОНТЕЙНЕРОВ"
echo "=============================================="
echo ""

# 1. Проверка Docker
echo "[1/5] Проверка Docker..."
if ! command -v docker &> /dev/null; then
    echo "   ❌ Docker не найден!"
    echo "   💡 Убедитесь, что Docker Desktop установлен и запущен"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "   ❌ Docker daemon не запущен!"
    echo "   💡 Запустите Docker Desktop и дождитесь полного запуска"
    exit 1
fi
echo "   ✅ Docker готов"
echo ""

# 2. Проверка сети
echo "[2/5] Проверка Docker сети..."
if ! docker network ls | grep -q atra-network; then
    docker network create atra-network
    echo "   ✅ Сеть atra-network создана"
else
    echo "   ✅ Сеть atra-network уже существует"
fi
echo ""

# 3. Проверка статуса контейнеров
echo "[3/5] Проверка статуса контейнеров..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    echo "   Текущий статус:"
    docker-compose -f knowledge_os/docker-compose.yml ps 2>&1 | grep -v "level=warning" || true
    echo ""

    # Singularity 15.0: Open WebUI (ask_victoria → Victoria) — поднимаем вместе с Victoria
    if ! docker ps --format "{{.Names}}" | grep -q "^open-webui$"; then
        echo "   🚀 Запуск Open WebUI (Singularity 15.0)..."
        docker-compose -f knowledge_os/docker-compose.yml up -d db redis victoria-agent open-webui 2>&1 | grep -v "level=warning" || true
        echo "   ⏳ Ожидание Victoria (10 сек)..."
        sleep 10
    fi
    # Явная проверка Victoria — если контейнер не запущен, поднимаем его первым
    if ! docker ps --format "{{.Names}}" | grep -q "^victoria-agent$"; then
        echo "   ⚠️  Victoria (victoria-agent) не запущена!"
        echo "   🚀 Запуск Victoria..."
        docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent 2>&1 | grep -v "level=warning" || true
        echo "   ⏳ Ожидание Victoria (10 сек)..."
        sleep 10
    fi

    # Проверка, какие контейнеры не запущены (up -d поднимает остановленные)
    NOT_RUNNING=$(docker-compose -f knowledge_os/docker-compose.yml ps 2>&1 | grep -E "Exit|Created|Stopped" | wc -l || echo "0")

    if [ "$NOT_RUNNING" -gt 0 ]; then
        echo "   ⚠️  Найдено не запущенных контейнеров: $NOT_RUNNING"
        echo "   🚀 Запуск контейнеров..."
        docker-compose -f knowledge_os/docker-compose.yml up -d 2>&1 | grep -v "level=warning" || true
        echo "   ⏳ Ожидание запуска (20 секунд)..."
        sleep 20
    else
        echo "   ✅ Все контейнеры Knowledge OS запущены"
    fi
    # Явная проверка оркестратора и Nightly Learner (задачи и обучение)
    if ! docker ps --format '{{.Names}}' | grep -q '^knowledge_nightly$'; then
        echo "   ⚠️  Nightly Learner не запущен — поднимаю..."
        docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_nightly 2>&1 | grep -v "level=warning" || true
        sleep 3
    fi
    if ! docker ps --format '{{.Names}}' | grep -q '^knowledge_os_orchestrator$'; then
        echo "   ⚠️  Orchestrator не запущен — поднимаю..."
        docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_os_orchestrator 2>&1 | grep -v "level=warning" || true
        sleep 3
    fi
else
    echo "   ❌ docker-compose.yml не найден!"
    exit 1
fi
echo ""

# 3.5 Drift guard for Open WebUI ask_victoria valves (must stay proxy-safe)
echo "   🔧 Проверка drift у ask_victoria valves..."
python3 scripts/ensure_openwebui_ask_victoria_valves.py || echo "   ⚠️ Не удалось автоисправить valves (проверьте open-webui/webui.db)"
echo "   🧭 Проверка policy Victoria (маршрутизация access/path запросов через ask_victoria)..."
python3 scripts/ensure_openwebui_victoria_policy.py || echo "   ⚠️ Не удалось автоисправить policy модели Victoria"
echo "   🧪 Проверка утечки reasoning-блоков без tool-call..."
python3 scripts/check_openwebui_reasoning_leak.py || echo "   ⚠️ Обнаружены недавние reasoning-ответы без tool-call (исторический след или policy drift)"
echo "   ♻️ Запуск авто-синхронизации policy для новых моделей Ollama..."
mkdir -p "$ROOT/logs" "$ROOT/.tmp"
if pgrep -f "openwebui_model_policy_watcher.py" >/dev/null 2>&1; then
    echo "   ✅ watcher уже запущен"
else
    nohup python3 "$ROOT/scripts/openwebui_model_policy_watcher.py" \
        >> "$ROOT/logs/openwebui_model_policy_watcher.log" 2>&1 &
    sleep 1
    if pgrep -f "openwebui_model_policy_watcher.py" >/dev/null 2>&1; then
        echo "   ✅ watcher запущен (лог: logs/openwebui_model_policy_watcher.log)"
    else
        echo "   ⚠️ не удалось запустить watcher (проверьте logs/openwebui_model_policy_watcher.log)"
    fi
fi
echo ""

# 4. Проверка доступности сервисов и автоперезапуск при сбое
echo "[4/5] Проверка доступности сервисов..."
echo ""

check_service() {
    local name=$1
    local url=$2
    if curl -s -f --connect-timeout 5 "$url" >/dev/null 2>&1; then
        echo "   ✅ $name: доступен"
        return 0
    else
        echo "   ❌ $name: недоступен"
        return 1
    fi
}

# Проверка трёх уровней Victoria (Agent, Enhanced, Initiative) — все должны быть true
check_victoria_levels() {
    local json
    json=$(curl -s --connect-timeout 5 "http://localhost:8010/status" 2>/dev/null) || return 1
    echo "$json" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    l = d.get('victoria_levels') or {}
    sys.exit(0 if (l.get('agent') and l.get('enhanced') and l.get('initiative')) else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null || return 1
}

SERVICES_OK=0
VICTORIA_OK=0
VERONICA_OK=0
check_service "Victoria (8010)" "http://localhost:8010/health" && { SERVICES_OK=$((SERVICES_OK + 1)); VICTORIA_OK=1; }
check_service "Veronica (8011)" "http://localhost:8011/health" && { SERVICES_OK=$((SERVICES_OK + 1)); VERONICA_OK=1; }
check_service "Ollama/MLX (11434)" "http://localhost:11434/api/tags" && SERVICES_OK=$((SERVICES_OK + 1))
# Knowledge OS REST API слушает порт 8002 (не 8000 — тот только внутри контейнеров)
check_service "Knowledge REST (8002)" "http://localhost:8002/health" && SERVICES_OK=$((SERVICES_OK + 1))
check_service "Open WebUI (3005)" "http://localhost:3005" || true

# 5. Автоперезапуск Victoria/Veronica при сбое; проверка трёх уровней Victoria
echo ""
echo "[5/5] Автоперезапуск при сбое и проверка Victoria (три уровня)..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    if [ "$VICTORIA_OK" -eq 0 ]; then
        echo "   ⚠️ Victoria не отвечает — перезапускаю victoria-agent..."
        docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent 2>&1 | grep -v "level=warning" || true
        sleep 10
        if check_service "Victoria (8010)" "http://localhost:8010/health"; then
            SERVICES_OK=$((SERVICES_OK + 1))
            echo "   ✅ Victoria поднялась после перезапуска"
        fi
    else
        # Initiative (Event Bus) поднимается асинхронно через 15–30 с после старта; при первом прогоне после загрузки системы даём время
        if ! check_victoria_levels; then
            echo "   ⚠️ Victoria: не все три уровня (agent/enhanced/initiative) активны — перезапускаю victoria-agent..."
            docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent 2>&1 | grep -v "level=warning" || true
            sleep 30
            if check_victoria_levels; then
                echo "   ✅ Victoria: все три уровня запущены после перезапуска"
            else
                echo "   ⚠️ Victoria: Enhanced/Initiative не поднялись (см. docker logs victoria-agent)"
            fi
        else
            echo "   ✅ Victoria: все три уровня (Agent, Enhanced, Initiative) активны"
        fi
    fi
    if [ "$VERONICA_OK" -eq 0 ]; then
        echo "   ⚠️ Veronica не отвечает — перезапускаю veronica-agent..."
        docker-compose -f knowledge_os/docker-compose.yml restart veronica-agent 2>&1 | grep -v "level=warning" || true
        sleep 10
        if check_service "Veronica (8011)" "http://localhost:8011/health"; then
            SERVICES_OK=$((SERVICES_OK + 1))
            echo "   ✅ Veronica поднялась после перезапуска"
        fi
    fi
fi

echo ""
echo "=============================================="
if [ $SERVICES_OK -eq 4 ]; then
    echo "✅ ВСЕ СЕРВИСЫ РАБОТАЮТ!"
else
    echo "⚠️  НЕКОТОРЫЕ СЕРВИСЫ НЕДОСТУПНЫ ($SERVICES_OK/4)"
    echo ""
    echo "💡 Проверьте логи:"
    echo "   docker-compose -f knowledge_os/docker-compose.yml logs [service_name]"
fi
echo "=============================================="
echo ""
echo "📊 Финальный статус контейнеров:"
docker-compose -f knowledge_os/docker-compose.yml ps 2>&1 | grep -v "level=warning" || true
echo ""
echo "🌐 Доступные сервисы:"
echo "   - Victoria: http://localhost:8010"
echo "   - Veronica: http://localhost:8011"
echo "   - Ollama/MLX: http://localhost:11434"
echo "   - Knowledge REST: http://localhost:8002"
echo "   - Open WebUI (Singularity 15.0): http://localhost:3005"
echo ""
