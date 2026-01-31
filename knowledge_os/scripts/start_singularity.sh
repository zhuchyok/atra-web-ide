#!/bin/bash
# Запуск Singularity 8.0

echo "🚀 Запуск Singularity 8.0..."
echo "=============================="
echo ""

# Проверка готовности
echo "📋 Проверка готовности системы..."
python3 knowledge_os/scripts/check_system_ready.py
if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️ Система не готова. Исправьте проблемы выше."
    exit 1
fi

echo ""
echo "✅ Система готова к запуску!"
echo ""

# Проверяем, запущены ли уже процессы
if pgrep -f "telegram_simple.py" > /dev/null; then
    echo "⚠️ Telegram бот уже запущен (PID: $(pgrep -f telegram_simple.py))"
    read -p "Остановить и перезапустить? (y/n): " answer
    if [ "$answer" = "y" ]; then
        pkill -f telegram_simple.py
        sleep 2
    else
        echo "Продолжаем с существующим процессом..."
    fi
fi

if pgrep -f "singularity_autonomous.py" > /dev/null; then
    echo "⚠️ Автономные компоненты уже запущены (PID: $(pgrep -f singularity_autonomous.py))"
    read -p "Остановить и перезапустить? (y/n): " answer
    if [ "$answer" = "y" ]; then
        pkill -f singularity_autonomous.py
        sleep 2
    else
        echo "Продолжаем с существующим процессом..."
    fi
fi

echo ""
echo "🚀 Запуск компонентов..."
echo ""

# Создаем директорию для логов если её нет
mkdir -p logs
echo "  📁 Директория для логов создана/проверена"

# Запуск Telegram бота в фоне
echo "📱 Запуск Telegram бота..."
nohup python3 knowledge_os/app/telegram_simple.py > logs/telegram.log 2>&1 &
TELEGRAM_PID=$!
echo "  ✅ Telegram бот запущен (PID: $TELEGRAM_PID)"

# Запуск автономных компонентов в фоне
echo "🤖 Запуск автономных компонентов..."
nohup python3 knowledge_os/app/singularity_autonomous.py > logs/singularity_autonomous.log 2>&1 &
AUTONOMOUS_PID=$!
echo "  ✅ Автономные компоненты запущены (PID: $AUTONOMOUS_PID)"

echo ""
echo "✅ Singularity 8.0 запущен!"
echo ""
echo "📊 Статус:"
echo "  - Telegram бот: PID $TELEGRAM_PID"
echo "  - Автономные компоненты: PID $AUTONOMOUS_PID"
echo ""
echo "📝 Логи:"
echo "  - Telegram: logs/telegram.log"
echo "  - Автономные: logs/singularity_autonomous.log"
echo ""
echo "🛑 Для остановки:"
echo "  pkill -f telegram_simple.py"
echo "  pkill -f singularity_autonomous.py"
echo ""

