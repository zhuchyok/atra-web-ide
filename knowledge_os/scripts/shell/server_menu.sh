#!/bin/bash

# ============================================================================
# ATRA Server Management Menu
# ============================================================================
# Скрипт меню для управления сервером ATRA
# Включает функции обновления, перезапуска, просмотра логов и работы с БД
# ============================================================================

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Пути
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
LOG_DIR="$PROJECT_DIR/logs"
DB_FILE="$PROJECT_DIR/atra.db"
LOCK_FILE="$PROJECT_DIR/atra.lock"
MAIN_SCRIPT="$PROJECT_DIR/main.py"

# Функция для отображения заголовка
show_header() {
    clear
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${WHITE}                           ATRA Server Management Menu                           ${CYAN}║${NC}"
    echo -e "${CYAN}║${WHITE}                        Система управления торговым ботом                        ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Функция для отображения главного меню
show_main_menu() {
    echo -e "${WHITE}📋 Главное меню:${NC}"
    echo ""
    echo -e "${GREEN}1.${NC} 🔄 Обновить код и перезапустить сервер"
    echo -e "${GREEN}2.${NC} 🚀 Перезапустить сервер"
    echo -e "${GREEN}3.${NC} 🛑 Остановить сервер"
    echo -e "${GREEN}4.${NC} 📊 Просмотр логов"
    echo -e "${GREEN}5.${NC} 🗄️  Работа с базой данных"
    echo -e "${GREEN}6.${NC} 📈 Статус системы"
    echo -e "${GREEN}7.${NC} 🔧 Системные утилиты"
    echo -e "${GREEN}8.${NC} 📁 Управление файлами"
    echo -e "${GREEN}9.${NC} ⚙️  Настройки"
    echo -e "${GREEN}0.${NC} 🚪 Выход"
    echo ""
    echo -e "${YELLOW}Выберите опцию (0-9):${NC} "
}

# Функция для проверки статуса сервера
check_server_status() {
    if [ -f "$LOCK_FILE" ]; then
        local pid=$(cat "$LOCK_FILE" 2>/dev/null)
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Сервер запущен (PID: $pid)${NC}"
            return 0
        else
            echo -e "${RED}❌ Lock файл существует, но процесс не найден${NC}"
            rm -f "$LOCK_FILE"
            return 1
        fi
    else
        echo -e "${RED}❌ Сервер не запущен${NC}"
        return 1
    fi
}

# Функция для обновления кода
update_code() {
    echo -e "${BLUE}🔄 Обновление кода из Git...${NC}"
    
    # Проверяем, что мы в Git репозитории
    if [ ! -d ".git" ]; then
        echo -e "${RED}❌ Не найден Git репозиторий${NC}"
        return 1
    fi
    
    # Сохраняем изменения
    echo -e "${YELLOW}💾 Сохранение локальных изменений...${NC}"
    git stash push -m "Auto-stash before update $(date)"
    
    # Получаем обновления
    echo -e "${YELLOW}📥 Получение обновлений из удаленного репозитория...${NC}"
    git fetch origin
    
    # Показываем доступные ветки
    echo -e "${YELLOW}🌿 Доступные ветки:${NC}"
    git branch -r | head -10
    
    # Спрашиваем, какую ветку обновить
    echo -e "${YELLOW}Введите название ветки для обновления (по умолчанию: insight):${NC}"
    read -r branch_name
    branch_name=${branch_name:-insight}
    
    # Переключаемся на ветку и обновляем
    echo -e "${YELLOW}🔄 Переключение на ветку $branch_name...${NC}"
    git checkout "$branch_name"
    git pull origin "$branch_name"
    
    # Восстанавливаем изменения
    echo -e "${YELLOW}🔄 Восстановление локальных изменений...${NC}"
    git stash pop
    
    echo -e "${GREEN}✅ Код успешно обновлен${NC}"
    return 0
}

# Функция для остановки сервера
stop_server() {
    echo -e "${YELLOW}🛑 Остановка сервера...${NC}"
    
    if [ -f "$LOCK_FILE" ]; then
        local pid=$(cat "$LOCK_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}📡 Отправка сигнала SIGTERM процессу $pid...${NC}"
            kill -TERM "$pid"
            
            # Ждем завершения процесса
            local count=0
            while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
                echo -e "${YELLOW}⏳ Ожидание завершения процесса... ($count/10)${NC}"
                sleep 1
                count=$((count + 1))
            done
            
            if ps -p "$pid" > /dev/null 2>&1; then
                echo -e "${RED}⚠️ Принудительное завершение процесса...${NC}"
                kill -KILL "$pid"
            fi
        fi
        
        rm -f "$LOCK_FILE"
        echo -e "${GREEN}✅ Сервер остановлен${NC}"
    else
        echo -e "${YELLOW}ℹ️ Lock файл не найден, попытка найти процесс по имени...${NC}"
        pkill -f "main.py"
        echo -e "${GREEN}✅ Все процессы main.py завершены${NC}"
    fi
}

# Функция для полного завершения процессов бота
kill_all_server_processes() {
    echo -e "${YELLOW}🔪 Полная остановка связанных процессов...${NC}"

    local patterns=(
        "main.py"
        "auto_execution.py"
        "ai_learning_system.py"
        "backfill_from_patterns.py"
        "backfill_trades_from_signals.py"
        "generate_historical_signals.py"
        "fallback_strategy.py"
        "scripts/backtest_fallback_strategy.py"
        "uvicorn"
        "fastapi"
        "atra/api"
    )

    local killed_any=false
    for pattern in "${patterns[@]}"; do
        if pgrep -f "$pattern" >/dev/null 2>&1; then
            pkill -f "$pattern" 2>/dev/null
            echo -e "${BLUE}   ⛔ Завершен процесс по шаблону:${NC} $pattern"
            killed_any=true
        fi
    done

    # Дополнительная страховка против висящих python-процессов внутри проекта
    if pgrep -f "python.*$PROJECT_DIR" >/dev/null 2>&1; then
        pkill -f "python.*$PROJECT_DIR" 2>/dev/null
        echo -e "${BLUE}   ⛔ Завершены вспомогательные python-процессы проекта${NC}"
        killed_any=true
    fi

    # Удаляем lock-файл если он остался
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid
        lock_pid=$(cat "$LOCK_FILE" 2>/dev/null)
        if [ -n "$lock_pid" ]; then
            if ps -p "$lock_pid" >/dev/null 2>&1; then
                echo -e "${YELLOW}   ⚠️ Завершение процесса из lock-файла (PID: $lock_pid)...${NC}"
                kill -TERM "$lock_pid" 2>/dev/null
                sleep 2
                if ps -p "$lock_pid" >/dev/null 2>&1; then
                    echo -e "${YELLOW}   ⚠️ SIGTERM не сработал, отправляем SIGKILL...${NC}"
                    kill -KILL "$lock_pid" 2>/dev/null
                    sleep 1
                fi
                if ps -p "$lock_pid" >/dev/null 2>&1; then
                    echo -e "${RED}   ❌ Процесс PID $lock_pid всё ещё активен${NC}"
                else
                    echo -e "${GREEN}   ✅ Процесс PID $lock_pid остановлен${NC}"
                    killed_any=true
                fi
            fi
        fi
        rm -f "$LOCK_FILE" 2>/dev/null
        echo -e "${BLUE}   🧹 Lock-файл удалён${NC}"
    fi

    if [ "$killed_any" = true ]; then
        sleep 2
        echo -e "${GREEN}✅ Все связанные процессы остановлены${NC}"
    else
        echo -e "${YELLOW}ℹ️ Активные процессы не обнаружены${NC}"
    fi

    # Финальная проверка
    if pgrep -f "main.py" >/dev/null 2>&1; then
        echo -e "${RED}   ❌ Обнаружены активные процессы main.py после очистки${NC}"
        pgrep -fal "main.py"
    fi
    if pgrep -f "uvicorn" >/dev/null 2>&1; then
        echo -e "${RED}   ❌ Обнаружены активные процессы uvicorn после очистки${NC}"
        pgrep -fal "uvicorn"
    fi
}

# Функция для запуска сервера
start_server() {
    echo -e "${BLUE}🚀 Запуск сервера...${NC}"
    
    # Проверяем, что сервер не запущен
    if check_server_status > /dev/null 2>&1; then
        echo -e "${RED}❌ Сервер уже запущен${NC}"
        return 1
    fi
    
    # Проверяем наличие main.py
    if [ ! -f "$MAIN_SCRIPT" ]; then
        echo -e "${RED}❌ Файл main.py не найден${NC}"
        return 1
    fi
    
    # Запускаем сервер в фоне
    echo -e "${YELLOW}🔄 Запуск сервера в фоновом режиме...${NC}"
    nohup python3 "$MAIN_SCRIPT" > "$LOG_DIR/server_output.log" 2>&1 &
    local pid=$!
    
    # Ждем немного и проверяем статус
    sleep 2
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Сервер успешно запущен (PID: $pid)${NC}"
        echo "$pid" > "$LOCK_FILE"
    else
        echo -e "${RED}❌ Ошибка запуска сервера${NC}"
        echo -e "${YELLOW}📋 Проверьте логи: tail -f $LOG_DIR/server_output.log${NC}"
    fi
}

# Функция для перезапуска сервера
restart_server() {
    echo -e "${BLUE}🔄 Перезапуск сервера...${NC}"
    kill_all_server_processes
    stop_server
    sleep 2
    start_server
}

# Функция для обновления и перезапуска
update_and_restart() {
    echo -e "${BLUE}🔄 Обновление кода и перезапуск сервера...${NC}"
    
    # Останавливаем сервер
    kill_all_server_processes
    stop_server
    
    # Обновляем код
    update_code
    
    # Запускаем сервер
    start_server
}

# Функция для просмотра логов
view_logs() {
    while true; do
        clear
        echo -e "${CYAN}📊 Просмотр логов${NC}"
        echo ""
        echo -e "${GREEN}1.${NC} 📋 Последние логи сервера"
        echo -e "${GREEN}2.${NC} 📈 Логи системы (system.log)"
        echo -e "${GREEN}3.${NC} 🔍 Поиск по логам"
        echo -e "${GREEN}4.${NC} 📊 Статистика логов"
        echo -e "${GREEN}5.${NC} 🧹 Очистка старых логов"
        echo -e "${GREEN}0.${NC} 🔙 Назад"
        echo ""
        echo -e "${YELLOW}Выберите опцию (0-5):${NC} "
        read -r choice
        
        case $choice in
            1)
                echo -e "${BLUE}📋 Последние логи сервера:${NC}"
                if [ -f "$LOG_DIR/server_output.log" ]; then
                    tail -50 "$LOG_DIR/server_output.log"
                else
                    echo -e "${RED}❌ Файл логов не найден${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            2)
                echo -e "${BLUE}📈 Логи системы:${NC}"
                if [ -f "$LOG_DIR/system.log" ]; then
                    tail -50 "$LOG_DIR/system.log"
                elif [ -f "system_improved.log" ]; then
                    tail -50 "system_improved.log"
                else
                    echo -e "${RED}❌ Основной файл системных логов не найден${NC}"
                    echo -e "${YELLOW}ℹ️ Ожидаемый путь: $LOG_DIR/system.log${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            3)
                echo -e "${YELLOW}Введите поисковый запрос:${NC}"
                read -r search_query
                echo -e "${BLUE}🔍 Результаты поиска '$search_query':${NC}"
                local search_targets=()
                if [ -f "system_improved.log" ]; then
                    search_targets+=("system_improved.log")
                fi
                local grep_output
                grep_output=$(grep -r "$search_query" "$LOG_DIR" "${search_targets[@]}" 2>/dev/null | head -20)
                if [ -n "$grep_output" ]; then
                    echo "$grep_output"
                else
                    echo -e "${YELLOW}ℹ️ Совпадений не найдено${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            4)
                echo -e "${BLUE}📊 Статистика логов:${NC}"
                echo -e "${YELLOW}Размер логов:${NC}"
                du -sh "$LOG_DIR" 2>/dev/null || echo "Логи не найдены"
                echo -e "${YELLOW}Количество файлов логов:${NC}"
                find "$LOG_DIR" -name "*.log" 2>/dev/null | wc -l
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            5)
                echo -e "${YELLOW}⚠️ Очистка логов старше 7 дней...${NC}"
                find "$LOG_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null
                echo -e "${GREEN}✅ Старые логи очищены${NC}"
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}❌ Неверный выбор${NC}"
                ;;
        esac
    done
}

# Функция для работы с базой данных
database_menu() {
    while true; do
        clear
        echo -e "${CYAN}🗄️ Работа с базой данных${NC}"
        echo ""
        echo -e "${GREEN}1.${NC} 📊 Информация о БД"
        echo -e "${GREEN}2.${NC} 🔍 Просмотр таблиц"
        echo -e "${GREEN}3.${NC} 📈 Статистика данных"
        echo -e "${GREEN}4.${NC} 🧹 Очистка БД"
        echo -e "${GREEN}5.${NC} 💾 Резервное копирование"
        echo -e "${GREEN}6.${NC} 🔄 Восстановление из резервной копии"
        echo -e "${GREEN}0.${NC} 🔙 Назад"
        echo ""
        echo -e "${YELLOW}Выберите опцию (0-6):${NC} "
        read -r choice
        
        case $choice in
            1)
                echo -e "${BLUE}📊 Информация о базе данных:${NC}"
                if [ -f "$DB_FILE" ]; then
                    echo -e "${YELLOW}Размер БД:${NC} $(du -sh "$DB_FILE" | cut -f1)"
                    echo -e "${YELLOW}Дата создания:${NC} $(stat -f "%Sm" "$DB_FILE" 2>/dev/null || stat -c "%y" "$DB_FILE" 2>/dev/null)"
                    echo -e "${YELLOW}Таблицы:${NC}"
                    sqlite3 "$DB_FILE" ".tables" 2>/dev/null || echo "Ошибка доступа к БД"
                else
                    echo -e "${RED}❌ База данных не найдена${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            2)
                echo -e "${BLUE}🔍 Просмотр таблиц:${NC}"
                if [ -f "$DB_FILE" ]; then
                    sqlite3 "$DB_FILE" ".schema" 2>/dev/null || echo "Ошибка доступа к БД"
                else
                    echo -e "${RED}❌ База данных не найдена${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            3)
                echo -e "${BLUE}📈 Статистика данных:${NC}"
                if [ -f "$DB_FILE" ]; then
                    echo -e "${YELLOW}Количество таблиц:${NC}"
                    sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null
                    echo -e "${YELLOW}Размер БД:${NC} $(du -sh "$DB_FILE" | cut -f1)"
                else
                    echo -e "${RED}❌ База данных не найдена${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            4)
                echo -e "${YELLOW}⚠️ Очистка базы данных...${NC}"
                echo -e "${RED}ВНИМАНИЕ: Это действие удалит все данные! Продолжить? (y/N):${NC}"
                read -r confirm
                if [[ $confirm =~ ^[Yy]$ ]]; then
                    rm -f "$DB_FILE"
                    echo -e "${GREEN}✅ База данных очищена${NC}"
                else
                    echo -e "${YELLOW}❌ Операция отменена${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            5)
                echo -e "${BLUE}💾 Создание резервной копии...${NC}"
                if [ -f "$DB_FILE" ]; then
                    local backup_name="backup_$(date +%Y%m%d_%H%M%S).db"
                    cp "$DB_FILE" "$backup_name"
                    echo -e "${GREEN}✅ Резервная копия создана: $backup_name${NC}"
                else
                    echo -e "${RED}❌ База данных не найдена${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            6)
                echo -e "${BLUE}🔄 Восстановление из резервной копии...${NC}"
                echo -e "${YELLOW}Доступные резервные копии:${NC}"
                ls -la backup_*.db 2>/dev/null || echo "Резервные копии не найдены"
                echo -e "${YELLOW}Введите имя файла резервной копии:${NC}"
                read -r backup_file
                if [ -f "$backup_file" ]; then
                    cp "$backup_file" "$DB_FILE"
                    echo -e "${GREEN}✅ База данных восстановлена из $backup_file${NC}"
                else
                    echo -e "${RED}❌ Файл резервной копии не найден${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}❌ Неверный выбор${NC}"
                ;;
        esac
    done
}

# Функция для проверки статуса системы
system_status() {
    clear
    echo -e "${CYAN}📈 Статус системы${NC}"
    echo ""
    
    # Статус сервера
    echo -e "${YELLOW}🖥️ Статус сервера:${NC}"
    check_server_status
    
    # Использование ресурсов
    echo -e "${YELLOW}💻 Использование ресурсов:${NC}"
    echo -e "${BLUE}CPU:${NC}"
    top -l 1 | grep "CPU usage" || echo "Информация о CPU недоступна"
    echo -e "${BLUE}Память:${NC}"
    top -l 1 | grep "PhysMem" || echo "Информация о памяти недоступна"
    
    # Дисковое пространство
    echo -e "${YELLOW}💾 Дисковое пространство:${NC}"
    df -h "$PROJECT_DIR" | tail -1
    
    # Размер проекта
    echo -e "${YELLOW}📁 Размер проекта:${NC}"
    du -sh "$PROJECT_DIR" 2>/dev/null
    
    # Последние логи
    echo -e "${YELLOW}📋 Последние записи в логах:${NC}"
    if [ -f "$LOG_DIR/server_output.log" ]; then
        tail -5 "$LOG_DIR/server_output.log"
    else
        echo "Логи не найдены"
    fi
    
    echo ""
    echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
    read -r
}

# Функция для системных утилит
system_utils() {
    while true; do
        clear
        echo -e "${CYAN}🔧 Системные утилиты${NC}"
        echo ""
        echo -e "${GREEN}1.${NC} 🧹 Очистка временных файлов"
        echo -e "${GREEN}2.${NC} 🔍 Проверка зависимостей"
        echo -e "${GREEN}3.${NC} 📊 Мониторинг процессов"
        echo -e "${GREEN}4.${NC} 🔄 Перезагрузка системы"
        echo -e "${GREEN}5.${NC} 📋 Информация о системе"
        echo -e "${GREEN}0.${NC} 🔙 Назад"
        echo ""
        echo -e "${YELLOW}Выберите опцию (0-5):${NC} "
        read -r choice
        
        case $choice in
            1)
                echo -e "${BLUE}🧹 Очистка временных файлов...${NC}"
                find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null
                find "$PROJECT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
                find "$PROJECT_DIR" -name "*.log" -mtime +7 -delete 2>/dev/null
                echo -e "${GREEN}✅ Временные файлы очищены${NC}"
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            2)
                echo -e "${BLUE}🔍 Проверка зависимостей...${NC}"
                python3 -c "import sys; print('Python версия:', sys.version)"
                pip3 list | grep -E "(telegram|sqlite|requests|pandas|numpy)" || echo "Основные зависимости не найдены"
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            3)
                echo -e "${BLUE}📊 Мониторинг процессов:${NC}"
                ps aux | grep -E "(python|main.py)" | grep -v grep
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            4)
                echo -e "${RED}⚠️ Перезагрузка системы...${NC}"
                echo -e "${YELLOW}Вы уверены? (y/N):${NC}"
                read -r confirm
                if [[ $confirm =~ ^[Yy]$ ]]; then
                    sudo reboot
                else
                    echo -e "${YELLOW}❌ Операция отменена${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            5)
                echo -e "${BLUE}📋 Информация о системе:${NC}"
                echo -e "${YELLOW}ОС:${NC} $(uname -a)"
                echo -e "${YELLOW}Время работы:${NC} $(uptime)"
                echo -e "${YELLOW}Свободная память:${NC} $(free -h 2>/dev/null || echo 'Информация недоступна')"
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}❌ Неверный выбор${NC}"
                ;;
        esac
    done
}

# Функция для управления файлами
file_management() {
    while true; do
        clear
        echo -e "${CYAN}📁 Управление файлами${NC}"
        echo ""
        echo -e "${GREEN}1.${NC} 📋 Список файлов проекта"
        echo -e "${GREEN}2.${NC} 🔍 Поиск файлов"
        echo -e "${GREEN}3.${NC} 📊 Размеры файлов"
        echo -e "${GREEN}4.${NC} 🗑️ Удаление файлов"
        echo -e "${GREEN}5.${NC} 📝 Редактирование файлов"
        echo -e "${GREEN}0.${NC} 🔙 Назад"
        echo ""
        echo -e "${YELLOW}Выберите опцию (0-5):${NC} "
        read -r choice
        
        case $choice in
            1)
                echo -e "${BLUE}📋 Список файлов проекта:${NC}"
                ls -la "$PROJECT_DIR" | head -20
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            2)
                echo -e "${YELLOW}Введите поисковый запрос:${NC}"
                read -r search_query
                echo -e "${BLUE}🔍 Результаты поиска '$search_query':${NC}"
                find "$PROJECT_DIR" -name "*$search_query*" 2>/dev/null | head -20
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            3)
                echo -e "${BLUE}📊 Размеры файлов:${NC}"
                du -sh "$PROJECT_DIR"/* 2>/dev/null | sort -hr | head -20
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            4)
                echo -e "${YELLOW}Введите имя файла для удаления:${NC}"
                read -r file_name
                if [ -f "$file_name" ]; then
                    echo -e "${RED}⚠️ Удалить файл $file_name? (y/N):${NC}"
                    read -r confirm
                    if [[ $confirm =~ ^[Yy]$ ]]; then
                        rm -f "$file_name"
                        echo -e "${GREEN}✅ Файл удален${NC}"
                    else
                        echo -e "${YELLOW}❌ Операция отменена${NC}"
                    fi
                else
                    echo -e "${RED}❌ Файл не найден${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            5)
                echo -e "${YELLOW}Введите имя файла для редактирования:${NC}"
                read -r file_name
                if [ -f "$file_name" ]; then
                    nano "$file_name"
                else
                    echo -e "${RED}❌ Файл не найден${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}❌ Неверный выбор${NC}"
                ;;
        esac
    done
}

# Функция для настроек
settings_menu() {
    while true; do
        clear
        echo -e "${CYAN}⚙️ Настройки${NC}"
        echo ""
        echo -e "${GREEN}1.${NC} 🔧 Настройки окружения"
        echo -e "${GREEN}2.${NC} 📝 Редактирование конфигурации"
        echo -e "${GREEN}3.${NC} 🔑 Настройки API ключей"
        echo -e "${GREEN}4.${NC} 📊 Настройки логирования"
        echo -e "${GREEN}0.${NC} 🔙 Назад"
        echo ""
        echo -e "${YELLOW}Выберите опцию (0-4):${NC} "
        read -r choice
        
        case $choice in
            1)
                echo -e "${BLUE}🔧 Настройки окружения:${NC}"
                echo -e "${YELLOW}Текущее окружение:${NC} $(grep ATRA_ENV env 2>/dev/null | cut -d'=' -f2 || echo 'Не найдено')"
                echo -e "${YELLOW}База данных:${NC} $(grep DATABASE env 2>/dev/null | cut -d'=' -f2 || echo 'Не найдено')"
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            2)
                echo -e "${BLUE}📝 Редактирование конфигурации:${NC}"
                if [ -f "env" ]; then
                    nano env
                else
                    echo -e "${RED}❌ Файл конфигурации не найден${NC}"
                fi
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            3)
                echo -e "${BLUE}🔑 Настройки API ключей:${NC}"
                echo -e "${YELLOW}Telegram Token:${NC} $(grep TELEGRAM_TOKEN env 2>/dev/null | cut -d'=' -f2 | cut -c1-10)..."
                echo -e "${YELLOW}Chat IDs:${NC} $(grep TELEGRAM_CHAT_IDS env 2>/dev/null | cut -d'=' -f2 || echo 'Не найдено')"
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            4)
                echo -e "${BLUE}📊 Настройки логирования:${NC}"
                echo -e "${YELLOW}Уровень логирования:${NC} $(grep -E "LOG_LEVEL|DEBUG" env 2>/dev/null || echo 'По умолчанию')"
                echo -e "${YELLOW}Ротация логов:${NC} $(grep -E "LOG_ROTATION|MAX_BYTES" env 2>/dev/null || echo 'По умолчанию')"
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}❌ Неверный выбор${NC}"
                ;;
        esac
    done
}

# Главный цикл меню
main() {
    # Создаем директорию для логов если её нет
    mkdir -p "$LOG_DIR"
    
    while true; do
        show_header
        show_main_menu
        read -r choice
        
        case $choice in
            1)
                update_and_restart
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            2)
                restart_server
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            3)
                stop_server
                echo ""
                echo -e "${YELLOW}Нажмите Enter для продолжения...${NC}"
                read -r
                ;;
            4)
                view_logs
                ;;
            5)
                database_menu
                ;;
            6)
                system_status
                ;;
            7)
                system_utils
                ;;
            8)
                file_management
                ;;
            9)
                settings_menu
                ;;
            0)
                echo -e "${GREEN}👋 До свидания!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ Неверный выбор. Попробуйте снова.${NC}"
                sleep 2
                ;;
        esac
    done
}

# Запуск главного меню
main
