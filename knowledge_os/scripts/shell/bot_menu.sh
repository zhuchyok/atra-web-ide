#!/bin/bash
# -*- coding: utf-8 -*-
# Интерактивное меню управления ботом ATRA

# Цвета для вывода (используем только для статуса, не для меню)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Проверка поддержки цветов
if [ -t 1 ]; then
    USE_COLORS=true
else
    USE_COLORS=false
fi

# Путь к директории бота
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BOT_DIR" || exit 1

# Функция для очистки экрана
clear_screen() {
    clear
}

# Функция для отображения заголовка
show_header() {
    if [ "$USE_COLORS" = true ]; then
        echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
        echo -e "${CYAN}║           ATRA BOT - МЕНЮ УПРАВЛЕНИЯ                    ║${NC}"
        echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    else
        echo "╔══════════════════════════════════════════════════════════╗"
        echo "║           ATRA BOT - МЕНЮ УПРАВЛЕНИЯ                    ║"
        echo "╚══════════════════════════════════════════════════════════╝"
    fi
    echo ""
}

# Функция для проверки статуса бота
check_bot_status() {
    if ps aux | grep -E "python.*main.py|python3.*main.py" | grep -v grep > /dev/null; then
        local pid=$(ps aux | grep -E "python.*main.py|python3.*main.py" | grep -v grep | awk '{print $2}' | head -1)
        local runtime=$(ps -p "$pid" -o etime= 2>/dev/null | tr -d ' ')
        if [ "$USE_COLORS" = true ]; then
            echo -e "${GREEN}✅ БОТ ЗАПУЩЕН${NC} (PID: $pid, Время работы: $runtime)"
        else
            echo "✅ БОТ ЗАПУЩЕН (PID: $pid, Время работы: $runtime)"
        fi
        return 0
    else
        if [ "$USE_COLORS" = true ]; then
            echo -e "${RED}❌ БОТ НЕ ЗАПУЩЕН${NC}"
        else
            echo "❌ БОТ НЕ ЗАПУЩЕН"
        fi
        return 1
    fi
}

# Функция для остановки бота
stop_bot() {
    echo -e "${YELLOW}🛑 Остановка бота...${NC}"
    pkill -9 -f "python.*main.py" 2>/dev/null
    pkill -9 -f "python3.*main.py" 2>/dev/null
    pkill -9 -f "uvicorn" 2>/dev/null
    pkill -9 -f "flask" 2>/dev/null
    rm -f bot.pid telegram_polling.lock 2>/dev/null
    sleep 1
    if ! ps aux | grep -E "python.*main.py" | grep -v grep > /dev/null; then
        echo -e "${GREEN}✅ Бот остановлен${NC}"
    else
        echo -e "${RED}❌ Ошибка при остановке${NC}"
    fi
    read -p "Нажмите Enter для продолжения..."
}

# Функция для запуска бота
start_bot() {
    if check_bot_status > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Бот уже запущен${NC}"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

    echo -e "${YELLOW}🚀 Запуск бота...${NC}"
    nohup python3 main.py > bot.log 2>&1 &
    sleep 2

    if check_bot_status > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Бот запущен${NC}"
    else
        echo -e "${RED}❌ Ошибка при запуске${NC}"
        echo "Проверьте логи: tail -f bot.log"
    fi
    read -p "Нажмите Enter для продолжения..."
}

# Функция для перезапуска бота
restart_bot() {
    echo -e "${YELLOW}🔄 Перезапуск бота...${NC}"
    stop_bot
    sleep 2
    start_bot
}

# Функция для просмотра логов в реальном времени
view_logs() {
    clear_screen
    show_header
    echo -e "${CYAN}📋 ПРОСМОТР ЛОГОВ (Ctrl+C для выхода)${NC}"
    echo ""
    echo -e "${YELLOW}Выберите режим:${NC}"
    echo "1) Все логи (tail -f)"
    echo "2) Только ошибки (ERROR)"
    echo "3) Только AUTO-исполнение"
    echo "4) Только сигналы (SIGNAL)"
    echo "5) Последние 50 строк"
    echo "6) Поиск по тексту"
    read -p "Выбор [1-6]: " log_choice

    case $log_choice in
        1)
            tail -f bot.log
            ;;
        2)
            tail -f bot.log | grep --color=always -i "ERROR\|CRITICAL\|EXCEPTION"
            ;;
        3)
            tail -f bot.log | grep --color=always -i "AUTO\|auto_exec\|автоисполнение"
            ;;
        4)
            tail -f bot.log | grep --color=always -i "SIGNAL\|сигнал\|BUY\|SELL"
            ;;
        5)
            tail -50 bot.log
            read -p "Нажмите Enter для продолжения..."
            ;;
        6)
            read -p "Введите текст для поиска: " search_text
            tail -f bot.log | grep --color=always -i "$search_text"
            ;;
        *)
            echo "Неверный выбор"
            sleep 1
            ;;
    esac
}

# Функция для обновления кода
update_code() {
    clear_screen
    show_header
    echo -e "${CYAN}🔄 ОБНОВЛЕНИЕ КОДА${NC}"
    echo ""

    if [ ! -d ".git" ]; then
        echo -e "${RED}❌ Директория не является git репозиторием${NC}"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

    echo -e "${YELLOW}Текущая ветка:${NC}"
    git branch --show-current
    echo ""
    echo -e "${YELLOW}Изменения:${NC}"
    git status --short
    echo ""
    echo -e "${YELLOW}Выберите действие:${NC}"
    echo "1) Обновить через git pull"
    echo "2) Обновить и перезапустить бота"
    echo "3) Показать git log"
    echo "4) Отменить"
    read -p "Выбор [1-4]: " update_choice

    case $update_choice in
        1)
            echo -e "${YELLOW}Обновление кода...${NC}"
            git pull
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ Код обновлен${NC}"
            else
                echo -e "${RED}❌ Ошибка при обновлении${NC}"
            fi
            read -p "Нажмите Enter для продолжения..."
            ;;
        2)
            echo -e "${YELLOW}Обновление кода и перезапуск...${NC}"
            git pull
            if [ $? -eq 0 ]; then
                echo -e "${GREEN}✅ Код обновлен${NC}"
                restart_bot
            else
                echo -e "${RED}❌ Ошибка при обновлении${NC}"
                read -p "Нажмите Enter для продолжения..."
            fi
            ;;
        3)
            git log --oneline -10
            read -p "Нажмите Enter для продолжения..."
            ;;
        4)
            return
            ;;
        *)
            echo "Неверный выбор"
            sleep 1
            ;;
    esac
}

# Функция для проверки статуса системы
system_status() {
    clear_screen
    show_header
    echo -e "${CYAN}📊 СТАТУС СИСТЕМЫ${NC}"
    echo ""

    echo -e "${YELLOW}Статус бота:${NC}"
    check_bot_status
    echo ""

    echo -e "${YELLOW}Процессы:${NC}"
    ps aux | grep -E "python.*main.py|uvicorn|flask" | grep -v grep | awk '{print "  PID: "$2", CPU: "$3"%, MEM: "$4"%, CMD: "$11" "$12" "$13}'
    echo ""

    echo -e "${YELLOW}Использование ресурсов:${NC}"
    echo "  CPU: $(top -l 1 | grep "CPU usage" | awk '{print $3}')"
    echo "  MEM: $(top -l 1 | grep "PhysMem" | awk '{print $2" "$3}')"
    echo ""

    echo -e "${YELLOW}Логи:${NC}"
    if [ -f "bot.log" ]; then
        local log_size=$(du -h bot.log | awk '{print $1}')
        local log_lines=$(wc -l < bot.log)
        echo "  Размер: $log_size"
        echo "  Строк: $log_lines"
        echo "  Последняя запись: $(tail -1 bot.log | cut -d'|' -f1 | head -1)"
    else
        echo "  Лог файл не найден"
    fi
    echo ""

    echo -e "${YELLOW}База данных:${NC}"
    if [ -f "trading.db" ]; then
        local db_size=$(du -h trading.db | awk '{print $1}')
        echo "  Размер: $db_size"
    else
        echo "  База данных не найдена"
    fi
    echo ""

    read -p "Нажмите Enter для продолжения..."
}

# Функция для быстрой проверки логов
quick_logs() {
    echo ""
    echo "📋 ПОСЛЕДНИЕ ЗАПИСИ В ЛОГЕ:"
    tail -15 bot.log 2>/dev/null | tail -10
    echo ""
}

# Функция для очистки логов
clear_logs() {
    echo -e "${YELLOW}🗑️  Очистка логов...${NC}"
    read -p "Вы уверены? (y/N): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        > bot.log
        echo -e "${GREEN}✅ Логи очищены${NC}"
    else
        echo "Отменено"
    fi
    read -p "Нажмите Enter для продолжения..."
}

# Функция для установки зависимостей
install_dependencies() {
    clear_screen
    show_header
    echo -e "${CYAN}📦 УСТАНОВКА ЗАВИСИМОСТЕЙ${NC}"
    echo ""

    if [ ! -f "requirements.txt" ]; then
        echo -e "${RED}❌ Файл requirements.txt не найден${NC}"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

    echo -e "${YELLOW}Обновление зависимостей...${NC}"
    pip3 install -r requirements.txt --upgrade
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

# Функция для показа статистики фильтров
show_filter_stats() {
    clear_screen
    show_header
    echo "📊 СТАТИСТИКА ФИЛЬТРОВ И СТАДИЙ ОБРАБОТКИ"
    echo ""
    read -p "За сколько часов показать статистику? [6]: " hours
    hours=${hours:-6}
    echo ""
    ./filter_stats.sh "$hours"
    echo ""
    read -p "Нажмите Enter для продолжения..."
}

# Функция для проверки базы данных
check_database() {
    clear_screen
    show_header
    echo -e "${CYAN}🗄️  ПРОВЕРКА БАЗЫ ДАННЫХ${NC}"
    echo ""

    if [ ! -f "trading.db" ]; then
        echo -e "${RED}❌ База данных не найдена${NC}"
        read -p "Нажмите Enter для продолжения..."
        return
    fi

    echo -e "${YELLOW}Статистика:${NC}"
    sqlite3 trading.db <<EOF
SELECT 'Пользователи в авто-режиме:' as info, COUNT(*) as count FROM user_settings WHERE trade_mode = 'auto';
SELECT 'Активные позиции:' as info, COUNT(*) as count FROM active_positions WHERE status = 'open';
SELECT 'Всего сигналов:' as info, COUNT(*) as count FROM accepted_signals;
SELECT 'Pending сигналы:' as info, COUNT(*) as count FROM accepted_signals WHERE status = 'pending';
EOF

    echo ""
    read -p "Нажмите Enter для продолжения..."
}

# Главное меню
main_menu() {
    while true; do
        clear_screen
        show_header

        # Статус бота
        echo "Статус:"
        check_bot_status
        echo ""

        # Быстрый просмотр логов
        quick_logs

        # Опции меню
        echo "Выберите действие:"
        echo ""
        echo "  1) ▶️  Запустить бота"
        echo "  2) ⏹️  Остановить бота"
        echo "  3) 🔄 Перезапустить бота"
        echo "  4) 📋 Просмотр логов (реальное время)"
        echo "  5) 🔄 Обновить код (git pull)"
        echo "  6) 📊 Статус системы"
        echo "  7) 🗄️  Проверка базы данных"
        echo "  8) 📦 Установить зависимости"
        echo "  9) 🗑️  Очистить логи"
        echo " 10) 📊 Статистика фильтров (таблица срезов)"
        echo "  0) ❌ Выход"
        echo ""

        read -p "Ваш выбор [0-9]: " choice

        case $choice in
            1)
                start_bot
                ;;
            2)
                stop_bot
                ;;
            3)
                restart_bot
                ;;
            4)
                view_logs
                ;;
            5)
                update_code
                ;;
            6)
                system_status
                ;;
            7)
                check_database
                ;;
            8)
                install_dependencies
                ;;
            9)
                clear_logs
                ;;
            10)
                show_filter_stats
                ;;
            0)
                echo -e "${YELLOW}Выход...${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Неверный выбор${NC}"
                sleep 1
                ;;
        esac
    done
}

# Запуск меню
main_menu
