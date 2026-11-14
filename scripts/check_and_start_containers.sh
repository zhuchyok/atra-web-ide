#!/bin/bash
# Проверка и запуск всех контейнеров на Mac Studio
# Запускать на Mac Studio: bash scripts/check_and_start_containers.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer real Docker Desktop binaries over any temporary mock PATH (CI/local smoke).
# ATRA_FORCE_PATH is a test-only override for deterministic fail-closed smoke.
if [ -n "${ATRA_FORCE_PATH:-}" ]; then
    export PATH="$ATRA_FORCE_PATH"
else
    export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:/usr/bin:/bin:$PATH"
fi
HARD_FAIL=0

run_compose_filtered() {
    local output
    set +e
    output=$("$@" 2>&1)
    local rc=$?
    set -e
    printf '%s\n' "$output" | grep -v "level=warning" || true
    return $rc
}

ensure_docker_network() {
    local name="$1"
    if docker network inspect "$name" >/dev/null 2>&1; then
        echo "   ✅ Сеть $name уже существует"
        return 0
    fi
    if docker network create "$name" >/dev/null 2>&1; then
        echo "   ✅ Сеть $name создана"
        return 0
    fi
    # Race: another process created it between inspect and create.
    if docker network inspect "$name" >/dev/null 2>&1; then
        echo "   ✅ Сеть $name уже существует"
        return 0
    fi
    echo "   ❌ Не удалось создать сеть $name"
    return 1
}

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
if ! ensure_docker_network "atra-network"; then
    HARD_FAIL=1
    exit 1
fi
echo ""

# 3. Проверка статуса контейнеров
echo "[3/5] Проверка статуса контейнеров..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    echo "   Текущий статус:"
    run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml ps || true
    echo ""

    # Singularity 15.0: Open WebUI (ask_victoria → Victoria) — поднимаем вместе с Victoria
    if ! docker ps --format "{{.Names}}" | grep -q "^open-webui$"; then
        echo "   🚀 Запуск Open WebUI (Singularity 15.0)..."
        if ! run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml up -d db redis victoria-agent open-webui; then
            echo "   ❌ Не удалось поднять Open WebUI/Victoria stack"
            HARD_FAIL=1
        fi
        echo "   ⏳ Ожидание Victoria (10 сек)..."
        sleep 10
    fi
    # Явная проверка Victoria — если контейнер не запущен, поднимаем его первым
    if ! docker ps --format "{{.Names}}" | grep -q "^victoria-agent$"; then
        echo "   ⚠️  Victoria (victoria-agent) не запущена!"
        echo "   🚀 Запуск Victoria..."
        if ! run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent; then
            echo "   ❌ Не удалось поднять victoria-agent"
            HARD_FAIL=1
        fi
        echo "   ⏳ Ожидание Victoria (10 сек)..."
        sleep 10
    fi

    # Проверка, какие контейнеры не запущены (up -d поднимает остановленные).
    # Avoid grep|wc||echo under pipefail (empty grep would corrupt the count).
    NOT_RUNNING=$(
      docker-compose -f knowledge_os/docker-compose.yml ps -a --status exited --status created 2>/dev/null \
        | wc -l \
        | tr -d '[:space:]'
    )
    NOT_RUNNING=${NOT_RUNNING:-0}

    if [ "$NOT_RUNNING" -gt 0 ]; then
        echo "   ⚠️  Найдено не запущенных контейнеров: $NOT_RUNNING"
        echo "   🚀 Запуск контейнеров..."
        if ! run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml up -d; then
            echo "   ❌ Не удалось поднять часть контейнеров"
            HARD_FAIL=1
        fi
        echo "   ⏳ Ожидание запуска (20 секунд)..."
        sleep 20
    else
        echo "   ✅ Все контейнеры Knowledge OS запущены"
    fi
    # Явная проверка оркестратора и Nightly Learner (задачи и обучение)
    # Guardrail: nightly может перегружать Ollama и мешать интерактивному чату Open WebUI.
    # Включать только явным флагом ENABLE_NIGHTLY_AUTOSTART=true.
    ENABLE_NIGHTLY_AUTOSTART=${ENABLE_NIGHTLY_AUTOSTART:-false}
    if ! docker ps --format '{{.Names}}' | grep -q '^knowledge_nightly$'; then
        if [ "$ENABLE_NIGHTLY_AUTOSTART" = "true" ]; then
            echo "   ⚠️  Nightly Learner не запущен — поднимаю (ENABLE_NIGHTLY_AUTOSTART=true)..."
            if ! run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_nightly; then
                echo "   ❌ Не удалось поднять knowledge_nightly"
                HARD_FAIL=1
            fi
            sleep 3
        else
            echo "   ⏭️  Nightly Learner отключен автозапуском (ENABLE_NIGHTLY_AUTOSTART=false)"
        fi
    fi
    if ! docker ps --format '{{.Names}}' | grep -q '^knowledge_os_orchestrator$'; then
        echo "   ⚠️  Orchestrator не запущен — поднимаю..."
        if ! run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_os_orchestrator; then
            echo "   ❌ Не удалось поднять knowledge_os_orchestrator"
            HARD_FAIL=1
        fi
        sleep 3
    fi
else
    echo "   ❌ docker-compose.yml не найден!"
    exit 1
fi
echo ""

# 3.5 Drift guard for Open WebUI ask_victoria valves (must stay proxy-safe)
echo "   🔧 Проверка drift у ask_victoria valves..."
if ! python3 scripts/ensure_openwebui_ask_victoria_valves.py; then
    echo "   ❌ Не удалось автоисправить valves (проверьте open-webui/webui.db)"
    HARD_FAIL=1
fi
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
if ! check_service "Open WebUI (3005)" "http://localhost:3005"; then
    HARD_FAIL=1
fi

# 5. Автоперезапуск Victoria/Veronica при сбое; проверка трёх уровней Victoria
echo ""
echo "[5/5] Автоперезапуск при сбое и проверка Victoria (три уровня)..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    if [ "$VICTORIA_OK" -eq 0 ]; then
        echo "   ⚠️ Victoria не отвечает — перезапускаю victoria-agent..."
        if ! run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent; then
            echo "   ❌ Ошибка перезапуска victoria-agent"
            HARD_FAIL=1
        fi
        sleep 10
        if check_service "Victoria (8010)" "http://localhost:8010/health"; then
            SERVICES_OK=$((SERVICES_OK + 1))
            echo "   ✅ Victoria поднялась после перезапуска"
        fi
    else
        # Initiative (Event Bus) поднимается асинхронно через 15–30 с после старта; при первом прогоне после загрузки системы даём время
        if ! check_victoria_levels; then
            echo "   ⚠️ Victoria: не все три уровня (agent/enhanced/initiative) активны — перезапускаю victoria-agent..."
            if ! run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent; then
                echo "   ❌ Ошибка перезапуска victoria-agent"
                HARD_FAIL=1
            fi
            sleep 30
            if check_victoria_levels; then
                echo "   ✅ Victoria: все три уровня запущены после перезапуска"
            else
                echo "   ⚠️ Victoria: Enhanced/Initiative не поднялись (см. docker logs victoria-agent)"
                HARD_FAIL=1
            fi
        else
            echo "   ✅ Victoria: все три уровня (Agent, Enhanced, Initiative) активны"
        fi
    fi
    if [ "$VERONICA_OK" -eq 0 ]; then
        echo "   ⚠️ Veronica не отвечает — перезапускаю veronica-agent..."
        if ! run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml restart veronica-agent; then
            echo "   ❌ Ошибка перезапуска veronica-agent"
            HARD_FAIL=1
        fi
        sleep 10
        if check_service "Veronica (8011)" "http://localhost:8011/health"; then
            SERVICES_OK=$((SERVICES_OK + 1))
            echo "   ✅ Veronica поднялась после перезапуска"
        fi
    fi
fi

echo ""
echo "=============================================="
if [ $SERVICES_OK -eq 4 ] && [ $HARD_FAIL -eq 0 ]; then
    echo "✅ ВСЕ СЕРВИСЫ РАБОТАЮТ!"
    EXIT_CODE=0
else
    echo "⚠️  НЕКОТОРЫЕ СЕРВИСЫ НЕДОСТУПНЫ ($SERVICES_OK/4)"
    echo ""
    echo "💡 Проверьте логи:"
    echo "   docker-compose -f knowledge_os/docker-compose.yml logs [service_name]"
    EXIT_CODE=1
fi
echo "=============================================="
echo ""
echo "📊 Финальный статус контейнеров:"
run_compose_filtered docker-compose -f knowledge_os/docker-compose.yml ps || true
echo ""
echo "🌐 Доступные сервисы:"
echo "   - Victoria: http://localhost:8010"
echo "   - Veronica: http://localhost:8011"
echo "   - Ollama/MLX: http://localhost:11434"
echo "   - Knowledge REST: http://localhost:8002"
echo "   - Open WebUI (Singularity 15.0): http://localhost:3005"
echo ""
exit $EXIT_CODE
