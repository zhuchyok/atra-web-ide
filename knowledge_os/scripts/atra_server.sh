#!/bin/bash

# ATRA Server Management Script
# Управление сервером ATRA с выбором компонентов

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/server_config.json"
MANAGER_SCRIPT="$SCRIPT_DIR/server_manager.py"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
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

# Проверка наличия Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 не найден. Установите Python3."
        exit 1
    fi
}

# Проверка наличия менеджера
check_manager() {
    if [ ! -f "$MANAGER_SCRIPT" ]; then
        log_error "Файл server_manager.py не найден"
        exit 1
    fi
}

# Показать статус
show_status() {
    log_info "Проверка статуса сервера..."
    python3 "$MANAGER_SCRIPT" status --config "$CONFIG_FILE"
}

# Запуск сервера
start_server() {
    log_info "Запуск сервера ATRA..."
    python3 "$MANAGER_SCRIPT" start --config "$CONFIG_FILE"
    if [ $? -eq 0 ]; then
        log_success "Сервер запущен"
    else
        log_error "Ошибка запуска сервера"
        exit 1
    fi
}

# Остановка сервера
stop_server() {
    log_info "Остановка сервера ATRA..."
    python3 "$MANAGER_SCRIPT" stop --config "$CONFIG_FILE"
    if [ $? -eq 0 ]; then
        log_success "Сервер остановлен"
    else
        log_error "Ошибка остановки сервера"
        exit 1
    fi
}

# Перезапуск сервера
restart_server() {
    log_info "Перезапуск сервера ATRA..."
    python3 "$MANAGER_SCRIPT" restart --config "$CONFIG_FILE"
    if [ $? -eq 0 ]; then
        log_success "Сервер перезапущен"
    else
        log_error "Ошибка перезапуска сервера"
        exit 1
    fi
}

# Включить компонент
enable_component() {
    local component="$1"
    if [ -z "$component" ]; then
        log_error "Укажите компонент для включения"
        echo "Доступные компоненты:"
        echo "  - core (основная система)"
        echo "  - telegram_bot (Telegram бот)"
        echo "  - ai_system (ИИ система)"
        echo "  - price_monitor (мониторинг цен)"
        echo "  - optimization (оптимизация)"
        echo "  - signals (генерация сигналов)"
        echo "  - monitoring (мониторинг системы)"
        echo "  - rest_api (REST API)"
        echo "  - web_dashboard (Web дашборд)"
        echo "  - auto_restart (автоперезапуск)"
        exit 1
    fi
    
    log_info "Включение компонента: $component"
    python3 "$MANAGER_SCRIPT" enable --component "$component" --config "$CONFIG_FILE"
}

# Отключить компонент
disable_component() {
    local component="$1"
    if [ -z "$component" ]; then
        log_error "Укажите компонент для отключения"
        echo "Доступные компоненты:"
        echo "  - core (основная система)"
        echo "  - telegram_bot (Telegram бот)"
        echo "  - ai_system (ИИ система)"
        echo "  - price_monitor (мониторинг цен)"
        echo "  - optimization (оптимизация)"
        echo "  - signals (генерация сигналов)"
        echo "  - monitoring (мониторинг системы)"
        echo "  - rest_api (REST API)"
        echo "  - web_dashboard (Web дашборд)"
        echo "  - auto_restart (автоперезапуск)"
        exit 1
    fi
    
    log_info "Отключение компонента: $component"
    python3 "$MANAGER_SCRIPT" disable --component "$component" --config "$CONFIG_FILE"
}

# Показать помощь
show_help() {
    echo "ATRA Server Management Script"
    echo ""
    echo "Использование: $0 [КОМАНДА] [ПАРАМЕТРЫ]"
    echo ""
    echo "КОМАНДЫ:"
    echo "  start                    - Запустить сервер"
    echo "  stop                     - Остановить сервер"
    echo "  restart                  - Перезапустить сервер"
    echo "  status                   - Показать статус"
    echo "  enable [компонент]       - Включить компонент"
    echo "  disable [компонент]      - Отключить компонент"
    echo "  config                  - Сохранить конфигурацию"
    echo "  help                     - Показать эту справку"
    echo ""
    echo "ПРИМЕРЫ:"
    echo "  $0 start                 # Запустить сервер"
    echo "  $0 status                # Показать статус"
    echo "  $0 enable monitoring     # Включить мониторинг"
    echo "  $0 disable auto_restart  # Отключить автоперезапуск"
    echo ""
    echo "КОМПОНЕНТЫ:"
    echo "  core          - Основная система (main.py)"
    echo "  telegram_bot  - Telegram бот"
    echo "  ai_system     - ИИ система"
    echo "  price_monitor - Мониторинг цен"
    echo "  optimization  - Система оптимизации"
    echo "  signals       - Генерация сигналов"
    echo "  monitoring    - Мониторинг системы"
    echo "  rest_api      - REST API"
    echo "  web_dashboard - Web дашборд"
    echo "  auto_restart  - Автоперезапуск"
}

# Основная логика
main() {
    check_python
    check_manager
    
    case "${1:-help}" in
        "start")
            start_server
            ;;
        "stop")
            stop_server
            ;;
        "restart")
            restart_server
            ;;
        "status")
            show_status
            ;;
        "enable")
            enable_component "$2"
            ;;
        "disable")
            disable_component "$2"
            ;;
        "config")
            log_info "Сохранение конфигурации..."
            python3 "$MANAGER_SCRIPT" config --config "$CONFIG_FILE"
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Неизвестная команда: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Запуск
main "$@"
