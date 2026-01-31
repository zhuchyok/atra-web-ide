#!/bin/bash
# Wrapper скрипт для автоматического перезапуска MLX API Server при падении

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MLX_SERVER="$PROJECT_ROOT/knowledge_os/app/mlx_api_server.py"
LOG_DIR="$PROJECT_ROOT/logs"
MAX_RESTARTS=10
RESTART_DELAY=5

# Создаем директорию для логов
mkdir -p "$LOG_DIR"

# Логирование
LOG_FILE="$LOG_DIR/mlx_server_wrapper.log"
echo "$(date '+%Y-%m-%d %H:%M:%S') - 🚀 Запуск MLX API Server wrapper" >> "$LOG_FILE"

restart_count=0

while [ $restart_count -lt $MAX_RESTARTS ]; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ✅ Запуск MLX API Server (попытка $((restart_count + 1))/$MAX_RESTARTS)" | tee -a "$LOG_FILE"
    
    # Запускаем сервер
    cd "$PROJECT_ROOT/knowledge_os/app" || exit 1
    python3 mlx_api_server.py 2>&1 | tee -a "$LOG_FILE"
    
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ✅ Сервер завершен нормально" | tee -a "$LOG_FILE"
        break
    else
        restart_count=$((restart_count + 1))
        echo "$(date '+%Y-%m-%d %H:%M:%S') - ⚠️ Сервер упал (код: $exit_code), перезапуск через $RESTART_DELAY секунд..." | tee -a "$LOG_FILE"
        
        if [ $restart_count -ge $MAX_RESTARTS ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') - ❌ Достигнут лимит перезапусков ($MAX_RESTARTS), остановка" | tee -a "$LOG_FILE"
            exit 1
        fi
        
        sleep $RESTART_DELAY
    fi
done
