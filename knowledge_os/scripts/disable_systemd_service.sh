#!/bin/bash

# Скрипт для отключения systemd сервиса и перехода на новую систему управления

echo "🛑 ОТКЛЮЧЕНИЕ SYSTEMD СЕРВИСА"
echo "================================"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 1. Остановить systemd сервис
log_info "Остановка systemd сервиса..."
sudo systemctl stop myproject.service 2>/dev/null || true
sudo systemctl stop atra.service 2>/dev/null || true

# 2. Отключить автозапуск
log_info "Отключение автозапуска systemd сервиса..."
sudo systemctl disable myproject.service 2>/dev/null || true
sudo systemctl disable atra.service 2>/dev/null || true

# 3. Остановить все процессы ATRA
log_info "Остановка всех процессов ATRA..."
pkill -f "main.py" 2>/dev/null || true
pkill -f "start_with_monitor" 2>/dev/null || true
pkill -f "system_monitor" 2>/dev/null || true
pkill -f "monitor_bot" 2>/dev/null || true
pkill -f "auto_restart" 2>/dev/null || true

# 4. Удалить файлы блокировки
log_info "Удаление файлов блокировки..."
rm -f atra.lock bot_restart_signal.txt 2>/dev/null || true

# 5. Перезагрузить systemd
log_info "Перезагрузка systemd..."
sudo systemctl daemon-reload

log_success "Systemd сервис отключен"

echo ""
log_info "🚀 Теперь используйте новую систему управления:"
echo ""
echo "  ./atra_server.sh start    - Запустить систему"
echo "  ./atra_server.sh stop     - Остановить систему"
echo "  ./atra_server.sh restart  - Перезапустить систему"
echo "  ./atra_server.sh status   - Показать статус"
echo ""
log_warning "⚠️  Systemd больше НЕ будет автоматически перезапускать систему!"
