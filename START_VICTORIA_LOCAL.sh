#!/bin/bash
# Скрипт для локального запуска Victoria Server с Victoria Initiative

cd "$(dirname "$0")"

echo "🚀 Запуск Victoria Server локально..."
echo ""

# Установка переменных окружения
export USE_VICTORIA_ENHANCED=true
export ENABLE_EVENT_MONITORING=true
export FILE_WATCHER_ENABLED=true
export SERVICE_MONITOR_ENABLED=true
export DEADLINE_TRACKER_ENABLED=true
export SKILLS_WATCHER_ENABLED=true

# Проверка переменных
echo "📋 Переменные окружения:"
echo "   USE_VICTORIA_ENHANCED=$USE_VICTORIA_ENHANCED"
echo "   ENABLE_EVENT_MONITORING=$ENABLE_EVENT_MONITORING"
echo ""

# Установка PYTHONPATH
export PYTHONPATH="$(pwd):$PYTHONPATH"
export PYTHONPATH="$(pwd)/knowledge_os:$PYTHONPATH"

# Запуск сервера
echo "🚀 Запуск Victoria Server..."
echo "   Порт: 8010"
echo "   URL: http://localhost:8010"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

python3 -m src.agents.bridge.victoria_server
