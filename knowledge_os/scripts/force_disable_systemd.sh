#!/bin/bash

# Принудительное отключение systemd сервиса

echo "🛑 ПРИНУДИТЕЛЬНОЕ ОТКЛЮЧЕНИЕ SYSTEMD СЕРВИСА"
echo "============================================="

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

# 1. Остановить ВСЕ systemd сервисы
log_info "Остановка ВСЕХ systemd сервисов..."
sudo systemctl stop myproject.service 2>/dev/null || true
sudo systemctl stop atra.service 2>/dev/null || true
sudo systemctl stop trading-bot.service 2>/dev/null || true
sudo systemctl stop bot.service 2>/dev/null || true

# 2. Отключить автозапуск ВСЕХ сервисов
log_info "Отключение автозапуска ВСЕХ сервисов..."
sudo systemctl disable myproject.service 2>/dev/null || true
sudo systemctl disable atra.service 2>/dev/null || true
sudo systemctl disable trading-bot.service 2>/dev/null || true
sudo systemctl disable bot.service 2>/dev/null || true

# 3. Удалить ВСЕ файлы сервисов
log_info "Удаление файлов systemd сервисов..."
sudo rm -f /etc/systemd/system/myproject.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/atra.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/trading-bot.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/bot.service 2>/dev/null || true

# 4. Остановить ВСЕ процессы Python
log_info "Остановка ВСЕХ процессов Python..."
sudo pkill -f "python.*main.py" 2>/dev/null || true
sudo pkill -f "python.*start_with_monitor" 2>/dev/null || true
sudo pkill -f "python.*system_monitor" 2>/dev/null || true
sudo pkill -f "python.*monitor_bot" 2>/dev/null || true
sudo pkill -f "python.*auto_restart" 2>/dev/null || true

# 5. Удалить ВСЕ файлы блокировки
log_info "Удаление ВСЕХ файлов блокировки..."
rm -f atra.lock 2>/dev/null || true
rm -f bot_restart_signal.txt 2>/dev/null || true
rm -f *.lock 2>/dev/null || true

# 6. Перезагрузить systemd
log_info "Перезагрузка systemd..."
sudo systemctl daemon-reload
sudo systemctl reset-failed

# 7. Проверить статус
log_info "Проверка статуса systemd сервисов..."
sudo systemctl status myproject.service 2>/dev/null || echo "myproject.service не найден"
sudo systemctl status atra.service 2>/dev/null || echo "atra.service не найден"

log_success "Systemd сервисы полностью отключены!"

echo ""
log_warning "⚠️  ВАЖНО: Теперь используйте ТОЛЬКО новую систему управления:"
echo ""
echo "  ./atra_server.sh start    - Запустить систему"
echo "  ./atra_server.sh stop     - Остановить систему"
echo "  ./atra_server.sh status   - Показать статус"
echo ""
log_info "🚀 Systemd больше НЕ будет перезапускать систему!"
