#!/bin/bash

# Скрипт для управления интегрированным ботом ATRA
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
LOG_FILE="$PROJECT_DIR/integrated_bot_simple.log"
PID_FILE="$PROJECT_DIR/integrated_bot_simple.pid"

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

# Функция для получения PID интегрированного бота
get_integrated_bot_pid() {
    ps aux | grep "integrated_bot_simple.py" | grep -v grep | awk '{print $2}' | head -1
}

# Функция для получения всех PID процессов ATRA
get_all_atra_pids() {
    ps aux | grep -E "(integrated_bot_simple|main.py|auto_optimization)" | grep -v grep | awk '{print $2}'
}

case "$1" in
    start)
        echo -e "${BLUE}🚀 Запуск интегрированного бота ATRA...${NC}"

        if is_running; then
            echo -e "${YELLOW}⚠️ Интегрированный бот уже запущен${NC}"
            exit 1
        fi

        cd "$PROJECT_DIR"

        # Запускаем интегрированный бот
        nohup python3 integrated_bot_simple.py > /dev/null 2>&1 &
        pid=$!

        # Сохраняем PID
        echo "$pid" > "$PID_FILE"

        # Ждем немного для инициализации
        sleep 3

        if is_running; then
            echo -e "${GREEN}✅ Интегрированный бот запущен (PID: $pid)${NC}"
            log "✅ Интегрированный бот запущен (PID: $pid)"
        else
            echo -e "${RED}❌ Ошибка запуска интегрированного бота${NC}"
            rm -f "$PID_FILE"
            exit 1
        fi
        ;;

    stop)
        echo -e "${BLUE}🛑 Остановка интегрированного бота ATRA...${NC}"

        # Останавливаем интегрированный бот
        integrated_pid=$(get_integrated_bot_pid)
        if [ ! -z "$integrated_pid" ]; then
            echo -e "${YELLOW}🔄 Останавливаем интегрированный бот (PID: $integrated_pid)...${NC}"
            kill "$integrated_pid"
            sleep 2

            # Принудительно останавливаем, если не остановился
            if ps -p "$integrated_pid" > /dev/null 2>&1; then
                echo -e "${YELLOW}⚠️ Принудительная остановка...${NC}"
                kill -9 "$integrated_pid"
            fi
        fi

        # Останавливаем все процессы ATRA
        all_pids=$(get_all_atra_pids)
        if [ ! -z "$all_pids" ]; then
            echo -e "${YELLOW}🔄 Останавливаем все процессы ATRA...${NC}"
            echo "$all_pids" | xargs kill
            sleep 2

            # Принудительно останавливаем оставшиеся процессы
            remaining_pids=$(get_all_atra_pids)
            if [ ! -z "$remaining_pids" ]; then
                echo -e "${YELLOW}⚠️ Принудительная остановка оставшихся процессов...${NC}"
                echo "$remaining_pids" | xargs kill -9
            fi
        fi

        # Удаляем PID файл
        rm -f "$PID_FILE"

        echo -e "${GREEN}✅ Интегрированный бот остановлен${NC}"
        log "🛑 Интегрированный бот остановлен"
        ;;

    restart)
        echo -e "${BLUE}🔄 Перезапуск интегрированного бота ATRA...${NC}"
        $0 stop
        sleep 2
        $0 start
        ;;

    status)
        echo -e "${BLUE}📊 Статус интегрированного бота ATRA:${NC}"
        echo ""

        # Проверяем интегрированный бот
        integrated_pid=$(get_integrated_bot_pid)
        if [ ! -z "$integrated_pid" ]; then
            echo -e "${GREEN}✅ Интегрированный бот: Запущен (PID: $integrated_pid)${NC}"
        else
            echo -e "${RED}❌ Интегрированный бот: Не запущен${NC}"
        fi

        # Проверяем все процессы ATRA
        echo ""
        echo -e "${BLUE}📋 Все процессы ATRA:${NC}"
        all_pids=$(get_all_atra_pids)
        if [ ! -z "$all_pids" ]; then
            ps aux | grep -E "(integrated_bot_simple|main.py|auto_optimization)" | grep -v grep | while read line; do
                pid=$(echo "$line" | awk '{print $2}')
                cmd=$(echo "$line" | awk '{print $11}')
                time=$(echo "$line" | awk '{print $10}')
                echo -e "  ${GREEN}PID: $pid${NC} - $cmd (время: $time)"
            done
        else
            echo -e "${RED}  Нет запущенных процессов${NC}"
        fi

        # Проверяем файл блокировки
        echo ""
        echo -e "${BLUE}📁 Файлы системы:${NC}"
        if [ -f "$PROJECT_DIR/atra.lock" ]; then
            lock_time=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$PROJECT_DIR/atra.lock")
            echo -e "  ${GREEN}atra.lock: Создан ($lock_time)${NC}"
        else
            echo -e "  ${RED}atra.lock: Отсутствует${NC}"
        fi

        # Показываем последние записи логов
        echo ""
        echo -e "${BLUE}📋 Последние записи логов:${NC}"
        if [ -f "$LOG_FILE" ]; then
            tail -5 "$LOG_FILE" | while read line; do
                echo "  $line"
            done
        else
            echo -e "  ${RED}Лог файл не найден${NC}"
        fi
        ;;

    logs)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo -e "${RED}❌ Лог файл не найден${NC}"
        fi
        ;;

    *)
        echo -e "${BLUE}🎯 Управление интегрированным ботом ATRA${NC}"
        echo ""
        echo "Использование: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Команды:"
        echo "  start   - Запустить интегрированный бот"
        echo "  stop    - Остановить интегрированный бот"
        echo "  restart - Перезапустить интегрированный бот"
        echo "  status  - Показать статус всех процессов"
        echo "  logs    - Показать логи в реальном времени"
        echo ""
        echo "Интегрированный бот включает:"
        echo "  🤖 Основной торговый бот (main.py)"
        echo "  ⚙️ Автоматическую оптимизацию (auto_optimization_scheduler.py)"
        echo "  📊 Мониторинг и перезапуск процессов"
        ;;
esac