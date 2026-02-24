#!/bin/bash
# Wrapper для автоперезапуска MLX API Server при падении (Metal OOM / SIGABRT).
# Использует те же env, что и start_mlx_api_server.sh: кэш 1, предзагрузка без 70B/104B.
# См. docs/MLX_PYTHON_CRASH_CAUSE.md
#
# Обход launchd exit 126: под launchd PATH минимальный, python3 может не находиться.
# Явно задаём PATH и PYTHON3 для надёжного запуска из LaunchAgent.

export PATH="${PATH:-/usr/bin:/bin}:/opt/homebrew/bin:/usr/local/bin"
if ! command -v python3 >/dev/null 2>&1; then
    for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
        [[ -x "$p" ]] && export PYTHON3="$p" && break
    done
fi
PYTHON3="${PYTHON3:-python3}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${ATRA_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
LOG_DIR="${LOG_DIR:-$HOME/Library/Logs/atra}"
MAX_RESTARTS=${MLX_WRAPPER_MAX_RESTARTS:-10}
RESTART_DELAY=${MLX_WRAPPER_RESTART_DELAY:-5}
MLX_PORT=${MLX_API_PORT:-11435}

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/mlx_server_wrapper.log"

# Те же ограничения, что в start_mlx_api_server.sh — меньше крашей (Metal OOM)
export MLX_ONLY_LIGHT=${MLX_ONLY_LIGHT:-true}
export MLX_MAX_CONCURRENT=${MLX_MAX_CONCURRENT:-1}
export MLX_MAX_CACHED_MODELS=${MLX_MAX_CACHED_MODELS:-1}
export VICTORIA_MLX_BRAIN=${VICTORIA_MLX_BRAIN:-false}
export MLX_PRELOAD_MODELS=${MLX_PRELOAD_MODELS:-fast}
export MLX_RATE_LIMIT_MAX=${MLX_RATE_LIMIT_MAX:-150}
export MLX_RATE_LIMIT_WINDOW=${MLX_RATE_LIMIT_WINDOW:-90}

echo "$(date '+%Y-%m-%d %H:%M:%S') - 🚀 Запуск MLX API Server wrapper (порт $MLX_PORT, перезапусков до $MAX_RESTARTS)" >> "$LOG_FILE"
restart_count=0

# Освобождаем порт перед первым и каждым перезапуском (избегаем Errno 48 address already in use)
kill_port() {
    local pid
    pid=$(lsof -ti ":$MLX_PORT" 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ⚠️ Освобождаю порт $MLX_PORT (PID: $pid)" | tee -a "$LOG_FILE"
        kill "$pid" 2>/dev/null || true
        sleep 2
    fi
}

while [ $restart_count -lt $MAX_RESTARTS ]; do
    kill_port
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ✅ Запуск MLX API Server (попытка $((restart_count + 1))/$MAX_RESTARTS)" | tee -a "$LOG_FILE"
    cd "$PROJECT_ROOT/knowledge_os" || exit 1
    "$PYTHON3" -m uvicorn app.mlx_api_server:app --host 0.0.0.0 --port "$MLX_PORT" --timeout-keep-alive 120 --log-level info 2>&1 | tee -a "$LOG_FILE"
    exit_code=${PIPESTATUS[0]}
    if [ $exit_code -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ✅ Сервер завершен нормально" | tee -a "$LOG_FILE"
        break
    fi
    restart_count=$((restart_count + 1))
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ⚠️ Сервер упал (код: $exit_code), перезапуск через ${RESTART_DELAY}с..." | tee -a "$LOG_FILE"
    [ $restart_count -ge $MAX_RESTARTS ] && { echo "$(date '+%Y-%m-%d %H:%M:%S') - ❌ Лимит перезапусков ($MAX_RESTARTS)" | tee -a "$LOG_FILE"; exit 1; }
    sleep "$RESTART_DELAY"
done
