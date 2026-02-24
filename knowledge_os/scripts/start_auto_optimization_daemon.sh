#!/bin/bash

# Скрипт для запуска автоматической оптимизации в качестве демона
# Автор: ATRA System
# Дата: 2025-08-07

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Путь к проекту
PROJECT_DIR="/Users/zhuchyok/Documents/GITHUB/atra"
LOG_FILE="$PROJECT_DIR/auto_optimization_daemon.log"
PID_FILE="$PROJECT_DIR/auto_optimization_daemon.pid"

# Функция для логирования
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Функция для проверки, запущен ли процесс
is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$PID_FILE"
        fi
    fi
    return 1
}

# Функция запуска
start() {
    log "${BLUE}🚀 Запуск демона автоматической оптимизации...${NC}"

    if is_running; then
        log "${YELLOW}⚠️ Демон уже запущен (PID: $(cat $PID_FILE))${NC}"
        return 1
    fi

    cd "$PROJECT_DIR"

    # Запускаем планировщик в фоновом режиме
    nohup python3 auto_optimization_scheduler.py > auto_optimization_scheduler.log 2>&1 &
    local pid=$!

    # Сохраняем PID
    echo "$pid" > "$PID_FILE"

    log "${GREEN}✅ Демон запущен с PID: $pid${NC}"
    log "${GREEN}📁 Логи: auto_optimization_scheduler.log${NC}"
    log "${GREEN}📁 PID файл: $PID_FILE${NC}"

    return 0
}

# Функция остановки
stop() {
    log "${BLUE}🛑 Остановка демона автоматической оптимизации...${NC}"

    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid"
            log "${GREEN}✅ Процесс $pid остановлен${NC}"
        else
            log "${YELLOW}⚠️ Процесс $pid уже не запущен${NC}"
        fi
        rm -f "$PID_FILE"
    else
        log "${YELLOW}⚠️ PID файл не найден${NC}"
    fi
}

# Функция перезапуска
restart() {
    log "${BLUE}🔄 Перезапуск демона автоматической оптимизации...${NC}"
    stop
    sleep 2
    start
}

# Функция проверки статуса
status() {
    if is_running; then
        local pid=$(cat "$PID_FILE")
        log "${GREEN}✅ Демон запущен (PID: $pid)${NC}"

        # Показываем последние логи
        echo ""
        log "${BLUE}📋 Последние записи логов:${NC}"
        tail -5 "$PROJECT_DIR/auto_optimization_scheduler.log" 2>/dev/null || echo "Логи не найдены"

        # Показываем статистику оптимизаций
        echo ""
        log "${BLUE}📊 Статистика оптимизаций:${NC}"
        if [ -f "$PROJECT_DIR/optimized_parameters.json" ]; then
            local last_modified=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$PROJECT_DIR/optimized_parameters.json")
            log "${GREEN}📅 Последняя оптимизация: $last_modified${NC}"
        else
            log "${YELLOW}⚠️ Файл параметров не найден${NC}"
        fi
    else
        log "${RED}❌ Демон не запущен${NC}"
    fi
}

# Функция показа помощи
show_help() {
    echo "🎯 Демон автоматической оптимизации ATRA"
    echo "========================================"
    echo ""
    echo "Использование: $0 {start|stop|restart|status|help}"
    echo ""
    echo "Команды:"
    echo "  start   - Запустить демон"
    echo "  stop    - Остановить демон"
    echo "  restart - Перезапустить демон"
    echo "  status  - Показать статус"
    echo "  help    - Показать эту справку"
    echo ""
    echo "Файлы:"
    echo "  Логи: auto_optimization_scheduler.log"
    echo "  PID: auto_optimization_daemon.pid"
    echo "  Параметры: optimized_parameters.json"
    echo ""
    echo "Расписание:"
    echo "  Ежедневная оптимизация: 06:00"
    echo "  Еженедельная полная оптимизация: воскресенье 08:00"
    echo "  Проверка производительности: каждые 4 часа"
}

# Основная логика
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ Неизвестная команда: $1"
        echo "Используйте: $0 help"
        exit 1
        ;;
esac

exit 0
