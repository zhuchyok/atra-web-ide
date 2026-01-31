#!/bin/bash
# Автоматический мониторинг моделей в MLX и Ollama
# Запускается периодически для отслеживания изменений

LOG_FILE="/tmp/model_monitor.log"
SCAN_INTERVAL=${MODEL_SCAN_INTERVAL:-3600}  # 1 час по умолчанию

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

scan_models() {
    log "🔍 Сканирование моделей..."
    
    # Запускаем Python скрипт сканирования
    cd "$(dirname "$0")/.."
    python3 scripts/scan_available_models.py >> "$LOG_FILE" 2>&1
    
    # Генерируем отчет об использовании
    python3 scripts/model_usage_report.py >> "$LOG_FILE" 2>&1
    
    log "✅ Сканирование завершено"
}

# Первое сканирование
scan_models

# Периодическое сканирование
while true; do
    sleep "$SCAN_INTERVAL"
    scan_models
done
