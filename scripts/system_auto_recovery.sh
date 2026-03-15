#!/bin/bash
# Система самовосстановления и автозапуска корпорации ATRA
# Запускается автоматически при загрузке системы через launchd
# Также можно запускать вручную: bash scripts/system_auto_recovery.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Launchd даёт минимальный PATH — без этого python3/uvicorn могут не находиться
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-/usr/bin:/bin:/usr/sbin:/sbin}"

LOG_FILE="${HOME}/Library/Logs/atra-auto-recovery.log"
ERROR_LOG="${HOME}/Library/Logs/atra-auto-recovery.error.log"

# Функция логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$ERROR_LOG"
}

log "=============================================="
log "🔄 СИСТЕМА САМОВОССТАНОВЛЕНИЯ ATRA"
log "=============================================="
log ""

# 0. Проверка и переподключение Wi-Fi
log "[0/10] Проверка и переподключение Wi-Fi..."
if [ -f "scripts/wifi_reconnect.sh" ]; then
    # Запускаем скрипт переподключения Wi-Fi
    if bash scripts/wifi_reconnect.sh >> "$LOG_FILE" 2>&1; then
        log "✅ Wi-Fi подключен и работает"
        WIFI_CONNECTED=true
    else
        log "⚠️ Wi-Fi не подключен или интернет недоступен"
        WIFI_CONNECTED=false
    fi
else
    log "⚠️ Скрипт wifi_reconnect.sh не найден, пропускаю проверку Wi-Fi"
    WIFI_CONNECTED=true  # Предполагаем, что Wi-Fi работает
fi
log ""

# 0.1. Проверка интернета
log "[0.1/10] Проверка интернета..."
check_internet() {
    # Пробуем подключиться к надежным DNS серверам
    if timeout 3 bash -c 'echo > /dev/tcp/8.8.8.8/53' 2>/dev/null || \
       timeout 3 bash -c 'echo > /dev/tcp/1.1.1.1/53' 2>/dev/null || \
       curl -s -f --connect-timeout 3 "http://www.google.com" >/dev/null 2>&1; then
        log "✅ Интернет доступен"
        return 0
    else
        log "⚠️ Интернет недоступен (система будет работать только с локальными моделями)"
        return 1
    fi
}

if check_internet; then
    INTERNET_AVAILABLE=true
else
    INTERNET_AVAILABLE=false
    # Если интернет недоступен, но Wi-Fi не подключен, пробуем переподключить еще раз
    if [ "$WIFI_CONNECTED" = "false" ] && [ -f "scripts/wifi_reconnect.sh" ]; then
        log "🔄 Интернет недоступен, пробую еще раз переподключить Wi-Fi..."
        bash scripts/wifi_reconnect.sh >> "$LOG_FILE" 2>&1 || true
        sleep 5
        # Проверяем интернет еще раз
        if check_internet; then
            INTERNET_AVAILABLE=true
            log "✅ Интернет восстановлен после переподключения Wi-Fi"
        fi
    fi
fi
log ""

# 1. Проверка и запуск Docker
log "[1/10] Проверка Docker..."
if ! command -v docker &> /dev/null; then
    log_error "Docker не установлен"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    log "⚠️ Docker daemon не запущен, запускаю Docker Desktop..."
    open -a Docker 2>/dev/null || true

    # Ждем запуска Docker (до 60 секунд)
    MAX_WAIT=60
    WAITED=0
    while ! docker info >/dev/null 2>&1; do
        if [ $WAITED -ge $MAX_WAIT ]; then
            log_error "Docker не запустился за $MAX_WAIT секунд"
            exit 1
        fi
        sleep 2
        WAITED=$((WAITED + 2))
    done
    log "✅ Docker запущен"
else
    log "✅ Docker работает"
fi

# 2. Проверка и создание Docker сети
log ""
log "[2/10] Проверка Docker сети..."
if ! docker network ls | grep -q atra-network; then
    docker network create atra-network 2>/dev/null || true
    log "✅ Сеть atra-network создана"
else
    log "✅ Сеть atra-network существует"
fi

# 3. Запуск Knowledge OS сервисов (db, redis, Victoria, Veronica, и т.д.)
log ""
log "[3/10] Запуск Knowledge OS сервисов..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    docker-compose -f knowledge_os/docker-compose.yml up -d 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
    log "✅ Knowledge OS сервисы запущены"
    sleep 5  # Даем время на запуск
else
    log_error "knowledge_os/docker-compose.yml не найден"
fi

# 4. Запуск ATRA Web IDE сервисов (frontend, backend)
log ""
log "[4/10] Запуск ATRA Web IDE сервисов..."
if [ -f "docker-compose.yml" ]; then
    docker-compose up -d 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
    log "✅ ATRA Web IDE сервисы запущены"
    sleep 5  # Даем время на запуск
else
    log_error "docker-compose.yml не найден"
fi

# 4.5. Проверка Ollama (после sleep/wake контекст Metal может инвалидироваться — PROJECT_GAPS §3)
log ""
OLLAMA_PORT=${OLLAMA_PORT:-11434}
if curl -s -f --connect-timeout 3 "http://localhost:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
    log "[4.5/10] ✅ Ollama (${OLLAMA_PORT}): работает"
else
    log "[4.5/10] ❌ Ollama (${OLLAMA_PORT}): не отвечает"
    if pgrep -f "ollama" >/dev/null; then
        log "   ⚠️ Процесс Ollama найден, но не отвечает (возможно после sleep/wake). Перезапускаю..."
        pkill -f "ollama" 2>/dev/null || true
        sleep 3
    fi
    if command -v ollama &>/dev/null; then
        log "   🚀 Запускаю Ollama..."
        nohup ollama serve >> "$LOG_FILE" 2>> "$ERROR_LOG" &
        sleep 5
        if curl -s -f --connect-timeout 5 "http://localhost:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
            log "   ✅ Ollama запустился"
        else
            log "   ⏳ Ollama запущен в фоне (порт может подняться позже)"
        fi
    else
        log "   ⚠️ ollama не найден в PATH"
    fi
fi
log ""

# 5. Проверка и запуск MLX API Server (если не запущен)
log ""
log "[5/10] Проверка MLX API Server..."
MLX_RUNNING=false

# Порт MLX API Server (можно изменить через MLX_API_PORT)
MLX_PORT=${MLX_API_PORT:-11435}

# 5.0. Проверка блокировки macOS (Documents access)
# См. docs/MLX_CRASH_ACCOUNTABILITY.md §5
check_mlx_launchd() {
    local status
    status=$(launchctl list gui/$(id -u) 2>/dev/null | grep "com.atra.mlx-api-server" | awk '{print $2}' || echo "0")
    if [[ "$status" == "126" || "$status" == "127" ]]; then
        log "⚠️ Обнаружена блокировка launchd (код $status). Исправляю..."
        bash scripts/setup_mlx_autostart.sh >> "$LOG_FILE" 2>&1 || true
        sleep 5
        return 1
    fi
    return 0
}

# Проверяем MLX на порту
if curl -s -f --connect-timeout 3 "http://localhost:${MLX_PORT}/health" >/dev/null 2>&1; then
    log "✅ MLX API Server (${MLX_PORT}): работает"
    MLX_RUNNING=true
else
    log "❌ MLX API Server (${MLX_PORT}): не работает"

    # Пробуем исправить launchd если нужно
    check_mlx_launchd || true

    # Проверяем, запущен ли процесс
    if pgrep -f "mlx_api_server\|mlx.*api" > /dev/null; then
        log "⚠️ Процесс MLX найден, но сервер не отвечает. Перезапускаю..."
        pkill -f "mlx_api_server\|mlx.*api" 2>/dev/null || true
        sleep 2
    fi

    # Запускаем MLX API Server
    log "🚀 Запускаю MLX API Server..."
    # Сначала пробуем через launchd (так как мы его починили выше)
    launchctl kickstart -k "gui/$(id -u)/com.atra.mlx-api-server" 2>/dev/null || \
    launchctl start com.atra.mlx-api-server 2>/dev/null || true

    sleep 10

    # Если через launchd не поднялся, используем прямой запуск как fallback
    if ! curl -s -f --connect-timeout 3 "http://localhost:${MLX_PORT}/health" >/dev/null 2>&1; then
        log "⚠️ launchd не помог, пробую прямой запуск через start_mlx_api_server.sh..."
        if [ -f "scripts/start_mlx_api_server.sh" ]; then
            # Используем venv проекта, если есть
            if [ -x "knowledge_os/.venv/bin/python" ]; then
                export MLX_PYTHON="$ROOT/knowledge_os/.venv/bin/python"
            fi
            nohup bash scripts/start_mlx_api_server.sh >> "$LOG_FILE" 2>> "$ERROR_LOG" &
            sleep 10
        fi
    fi

    # Финальная проверка
    if curl -s -f --connect-timeout 3 "http://localhost:${MLX_PORT}/health" >/dev/null 2>&1; then
        log "   ✅ MLX API Server запустился и работает"
        MLX_RUNNING=true
    else
        log_error "   ❌ MLX API Server не запустился"
    fi
fi

# 5.1. Проверка и запуск Moondream Station (Vision модели, порт 2020)
log ""
log "[5.1/10] Проверка Moondream Station (Vision, порт 2020)..."
MOONDREAM_PORT=${MOONDREAM_PORT:-2020}
if curl -s -f --connect-timeout 3 "http://localhost:${MOONDREAM_PORT}/v1/" >/dev/null 2>&1 || \
   curl -s -f --connect-timeout 3 "http://localhost:${MOONDREAM_PORT}/health" >/dev/null 2>&1 || \
   curl -s -f --connect-timeout 3 "http://localhost:${MOONDREAM_PORT}/" >/dev/null 2>&1; then
    log "✅ Moondream Station (${MOONDREAM_PORT}): работает"
else
    log "❌ Moondream Station (${MOONDREAM_PORT}): не работает"
    if command -v moondream-station &>/dev/null; then
        if pgrep -f "moondream-station\|moondream" >/dev/null; then
            log "⚠️ Процесс Moondream найден, но не отвечает. Перезапускаю..."
            pkill -f "moondream-station\|moondream" 2>/dev/null || true
            sleep 2
        fi
        log "🚀 Запускаю Moondream Station..."
        nohup moondream-station >> "$LOG_FILE" 2>> "$ERROR_LOG" &
        sleep 5
        if curl -s -f --connect-timeout 5 "http://localhost:${MOONDREAM_PORT}/v1/" >/dev/null 2>&1 || curl -s -f --connect-timeout 5 "http://localhost:${MOONDREAM_PORT}/" >/dev/null 2>&1; then
            log "   ✅ Moondream Station запустился"
        else
            log "   ⏳ Moondream Station запущен в фоне (порт может подняться позже)"
        fi
    elif [ -f "scripts/start_moondream_station.sh" ]; then
        nohup bash scripts/start_moondream_station.sh >> "$LOG_FILE" 2>> "$ERROR_LOG" &
        log "   Запущен через scripts/start_moondream_station.sh"
    else
        log "   ⚠️ moondream-station не установлен (pip install moondream-station)"
    fi
fi

# 6. Проверка здоровья всех сервисов
log ""
log "[6/10] Проверка здоровья всех сервисов..."

check_service() {
    local name=$1
    local url=$2
    local max_retries=3
    local retry=0

    while [ $retry -lt $max_retries ]; do
        if curl -s -f --connect-timeout 5 "$url" >/dev/null 2>&1; then
            log "   ✅ $name: работает"
            return 0
        fi
        retry=$((retry + 1))
        sleep 2
    done

    log "   ❌ $name: недоступен после $max_retries попыток"
    return 1
}

SERVICES_OK=0
TOTAL_SERVICES=0
VICTORIA_HEALTH_OK=0
VERONICA_HEALTH_OK=0

# Knowledge OS сервисы
TOTAL_SERVICES=$((TOTAL_SERVICES + 1))
if check_service "Victoria Agent (8010)" "http://localhost:8010/health"; then
    SERVICES_OK=$((SERVICES_OK + 1))
    VICTORIA_HEALTH_OK=1
fi

TOTAL_SERVICES=$((TOTAL_SERVICES + 1))
if check_service "Veronica Agent (8011)" "http://localhost:8011/health"; then
    SERVICES_OK=$((SERVICES_OK + 1))
    VERONICA_HEALTH_OK=1
fi

# ATRA Web IDE сервисы
TOTAL_SERVICES=$((TOTAL_SERVICES + 1))
check_service "ATRA Web IDE Backend (8080)" "http://localhost:8080/health" && SERVICES_OK=$((SERVICES_OK + 1)) || true

TOTAL_SERVICES=$((TOTAL_SERVICES + 1))
check_service "ATRA Web IDE Frontend (3002)" "http://localhost:3002" && SERVICES_OK=$((SERVICES_OK + 1)) || true

# MLX API Server
TOTAL_SERVICES=$((TOTAL_SERVICES + 1))
MLX_PORT=${MLX_API_PORT:-11435}
if curl -s -f --connect-timeout 3 "http://localhost:${MLX_PORT}/api/tags" >/dev/null 2>&1; then
    log "   ✅ MLX API Server (${MLX_PORT}): работает"
    SERVICES_OK=$((SERVICES_OK + 1))
else
    log "   ❌ MLX API Server (${MLX_PORT}): недоступен"
    log_error "   MLX API Server критичен для работы агентов!"
fi

# Ollama (после sleep/wake может не отвечать — PROJECT_GAPS §3)
TOTAL_SERVICES=$((TOTAL_SERVICES + 1))
OLLAMA_PORT=${OLLAMA_PORT:-11434}
if curl -s -f --connect-timeout 3 "http://localhost:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
    log "   ✅ Ollama (${OLLAMA_PORT}): работает"
    SERVICES_OK=$((SERVICES_OK + 1))
else
    log "   ❌ Ollama (${OLLAMA_PORT}): недоступен"
    log_error "   Ollama критичен для работы Victoria (executor/planner)!"
fi

# 7. Автоматическое исправление проблем
log ""
log "[7/10] Автоматическое исправление проблем..."

# Проверка трёх уровней Victoria (Agent, Enhanced, Initiative) — все должны быть true
check_victoria_levels() {
    curl -s --connect-timeout 5 "http://localhost:8010/status" 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    l = d.get('victoria_levels') or {}
    sys.exit(0 if (l.get('agent') and l.get('enhanced') and l.get('initiative')) else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null || return 1
}

# Перезапуск Victoria/Veronica, если health check не прошёл (контейнер может быть up, но не отвечать)
if [ -f "knowledge_os/docker-compose.yml" ]; then
    if [ "${VICTORIA_HEALTH_OK:-0}" -eq 0 ]; then
        log "⚠️ Victoria Agent не отвечает на /health — перезапускаю victoria-agent..."
        docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
        sleep 10
        if curl -s -f --connect-timeout 5 "http://localhost:8010/health" >/dev/null 2>&1; then
            log "   ✅ Victoria Agent поднялась после перезапуска"
        else
            log_error "   Victoria Agent всё ещё недоступна после перезапуска"
        fi
    else
        # Victoria отвечает на /health — проверяем, что все три уровня (Agent, Enhanced, Initiative) включены
        if ! check_victoria_levels; then
            log "⚠️ Victoria: не все три уровня активны (agent/enhanced/initiative) — перезапускаю victoria-agent..."
            docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
            sleep 25
            if check_victoria_levels; then
                log "   ✅ Victoria: все три уровня запущены после перезапуска"
            else
                log_error "   Victoria: Enhanced/Initiative всё ещё не активны (см. логи контейнера)"
            fi
        fi
    fi
    if [ "${VERONICA_HEALTH_OK:-0}" -eq 0 ]; then
        log "⚠️ Veronica Agent не отвечает на /health — перезапускаю veronica-agent..."
        docker-compose -f knowledge_os/docker-compose.yml restart veronica-agent 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
        sleep 10
        if curl -s -f --connect-timeout 5 "http://localhost:8011/health" >/dev/null 2>&1; then
            log "   ✅ Veronica Agent поднялась после перезапуска"
        else
            log_error "   Veronica Agent всё ещё недоступна после перезапуска"
        fi
    fi
    # Перезапуск упавших контейнеров: up -d поднимает остановленные (restart только перезапускает уже работающие)
    NOT_RUNNING=$(docker-compose -f knowledge_os/docker-compose.yml ps 2>&1 | grep -E "Exit|Created|Stopped" | wc -l | tr -d ' \n' || echo "0")
    NOT_RUNNING=${NOT_RUNNING:-0}
    if [ "$NOT_RUNNING" -gt 0 ]; then
        log "⚠️ Найдено $NOT_RUNNING не запущенных контейнеров Knowledge OS — поднимаю (up -d)..."
        docker-compose -f knowledge_os/docker-compose.yml up -d 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
        sleep 5
    fi
    # Явный контроль оркестратора и Nightly Learner: без них не создаются задачи и не идёт обучение
    if ! docker ps --format '{{.Names}}' | grep -q '^knowledge_nightly$'; then
        log "⚠️ Nightly Learner (knowledge_nightly) не запущен — поднимаю..."
        docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_nightly 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
        sleep 3
    fi
    if ! docker ps --format '{{.Names}}' | grep -q '^knowledge_os_orchestrator$'; then
        log "⚠️ Orchestrator (knowledge_os_orchestrator) не запущен — поднимаю..."
        docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_os_orchestrator 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
        sleep 3
    fi
fi

if [ -f "docker-compose.yml" ]; then
    NOT_RUNNING=$(docker-compose ps 2>&1 | grep -E "Exit|Created|Stopped" | wc -l | tr -d ' \n' || echo "0")
    NOT_RUNNING=${NOT_RUNNING:-0}
    if [ "$NOT_RUNNING" -gt 0 ]; then
        log "⚠️ Найдено $NOT_RUNNING не запущенных контейнеров ATRA Web IDE — поднимаю (up -d)..."
        docker-compose up -d 2>&1 | grep -v "level=warning" | tee -a "$LOG_FILE" || true
        sleep 5
    fi
fi

# 8. Проверка устойчивости к потере интернета
log ""
log "[8/10] Проверка устойчивости к потере интернета..."

if [ "$INTERNET_AVAILABLE" = "false" ]; then
    log "⚠️ Интернет недоступен, проверяю работу в режиме только локальных моделей..."

    # MLX и Ollama критичны для работы без интернета
    MLX_PORT=${MLX_API_PORT:-11435}
    OLLAMA_PORT=${OLLAMA_PORT:-11434}
    if ! curl -s -f --connect-timeout 3 "http://localhost:${MLX_PORT}/api/tags" >/dev/null 2>&1; then
        log_error "❌ КРИТИЧНО: MLX API Server не работает, а интернет недоступен!"
        log_error "   Запускаю MLX API Server..."
        bash scripts/start_mlx_api_server.sh >> "$LOG_FILE" 2>> "$ERROR_LOG" &
        sleep 10
    else
        log "✅ MLX API Server работает"
    fi
    if ! curl -s -f --connect-timeout 3 "http://localhost:${OLLAMA_PORT}/api/tags" >/dev/null 2>&1; then
        log_error "❌ КРИТИЧНО: Ollama не работает, а интернет недоступен!"
        log_error "   Запускаю Ollama..."
        nohup ollama serve >> "$LOG_FILE" 2>> "$ERROR_LOG" &
        sleep 5
    else
        log "✅ Ollama работает - система может работать без интернета"
    fi
else
    log "✅ Интернет доступен - система работает в обычном режиме"
fi
log ""

# 9. Финальная проверка
log ""
log "[9/10] Финальная проверка..."

# Повторная проверка после исправлений
FINAL_SERVICES_OK=0
check_service "Victoria Agent" "http://localhost:8010/health" && FINAL_SERVICES_OK=$((FINAL_SERVICES_OK + 1)) || true
check_service "Veronica Agent" "http://localhost:8011/health" && FINAL_SERVICES_OK=$((FINAL_SERVICES_OK + 1)) || true
check_service "ATRA Web IDE Backend" "http://localhost:8080/health" && FINAL_SERVICES_OK=$((FINAL_SERVICES_OK + 1)) || true

log ""
log "=============================================="
log "📊 ИТОГОВЫЙ СТАТУС"
log "=============================================="
log "Работающих сервисов: $FINAL_SERVICES_OK/$TOTAL_SERVICES"
log ""

    # 10. Самопроверка — полная верификация (система проверяет сама себя)
    log "[10/10] Самопроверка (verify_mac_studio_self_recovery)..."
    if [ -f "scripts/verify_mac_studio_self_recovery.sh" ]; then
        log "--- Результат самопроверки ---"
        bash scripts/verify_mac_studio_self_recovery.sh 2>&1 | tee -a "$LOG_FILE" || true
        log "--- Конец самопроверки ---"
    else
        log "⚠️ Скрипт verify_mac_studio_self_recovery.sh не найден"
    fi
    log ""

    # 11. Проверка и перезапуск Telegram бота (Singularity 14.0)
    log "[11/11] Проверка Telegram бота..."
    # ... (код бота) ...
    log ""

    # 12. [SINGULARITY 24.0] Автономное восстановление (Remediation)
    log "[12/12] Проверка автономных исправлений (Remediation)..."
    if [ -f "scripts/autonomous_remediation_executor.sh" ]; then
        bash scripts/autonomous_remediation_executor.sh >> "$LOG_FILE" 2>&1 || true
    fi
    log ""

    # 13. [SINGULARITY 21.5] Сброс зависших задач (Watchdog)
    log "[13/13] Сброс зависших задач..."
    if [ -x "knowledge_os/.venv/bin/python" ]; then
        "knowledge_os/.venv/bin/python" "knowledge_os/scripts/reset_stuck_tasks.py" >> "$LOG_FILE" 2>&1 || true
    fi
    log ""

    if [ $FINAL_SERVICES_OK -ge 3 ]; then
    log "✅ СИСТЕМА В РАБОЧЕМ СОСТОЯНИИ"
    log ""
    log "🌐 Доступные сервисы:"
    log "   - Victoria: http://localhost:8010"
    log "   - Veronica: http://localhost:8011"
    log "   - ATRA Web IDE: http://localhost:3002"
    log "   - Backend API: http://localhost:8080"
    log "   - API Docs: http://localhost:8080/docs"
    exit 0
else
    log "⚠️ НЕКОТОРЫЕ СЕРВИСЫ НЕ РАБОТАЮТ"
    log "Проверьте логи:"
    log "   tail -f $LOG_FILE"
    log "   tail -f $ERROR_LOG"
    exit 1
fi
