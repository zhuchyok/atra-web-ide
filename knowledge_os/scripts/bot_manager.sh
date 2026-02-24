#!/bin/bash

# Скрипт для управления Telegram ботом
# Использование: ./bot_manager.sh [start|stop|restart|status|monitor]

BOT_PROCESS="main.py"
LOCK_FILE="atra.lock"

case "$1" in
    start)
        echo "🚀 Запуск бота..."
        if [ -f "$LOCK_FILE" ]; then
            echo "⚠️  Бот уже запущен (найден файл блокировки)"
            echo "💡 Используйте './bot_manager.sh stop' для остановки"
            exit 1
        fi
        python3 main.py &
        echo "✅ Бот запущен в фоновом режиме"
        ;;
    stop)
        echo "🛑 Остановка бота..."
        pkill -f "$BOT_PROCESS"
        if [ -f "$LOCK_FILE" ]; then
            rm "$LOCK_FILE"
            echo "🔓 Файл блокировки удален"
        fi
        echo "✅ Бот остановлен"
        ;;
    restart)
        echo "🔄 Перезапуск бота..."
        ./bot_manager.sh stop
        sleep 2
        ./bot_manager.sh start
        ;;
    status)
        echo "📊 Статус бота:"
        if pgrep -f "$BOT_PROCESS" > /dev/null; then
            echo "✅ Бот запущен"
            echo "📋 Процессы:"
            ps aux | grep "$BOT_PROCESS" | grep -v grep
        else
            echo "❌ Бот не запущен"
        fi

        if [ -f "$LOCK_FILE" ]; then
            echo "🔒 Файл блокировки найден"
        else
            echo "🔓 Файл блокировки отсутствует"
        fi
        ;;
    monitor)
        echo "🔍 Запуск мониторинга..."
        python3 monitor_bot.py
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|monitor}"
        echo ""
        echo "Команды:"
        echo "  start   - Запустить бота"
        echo "  stop    - Остановить бота"
        echo "  restart - Перезапустить бота"
        echo "  status  - Показать статус"
        echo "  monitor - Запустить мониторинг"
        exit 1
        ;;
esac
