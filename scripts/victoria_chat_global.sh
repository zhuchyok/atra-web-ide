#!/bin/bash
# Глобальный скрипт для запуска Victoria Chat из любой директории
# Использование: bash ~/Documents/atra-web-ide/scripts/victoria_chat_global.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Проверка существования проекта
if [ ! -f "$PROJECT_ROOT/scripts/victoria_chat.py" ]; then
    echo "❌ Проект atra-web-ide не найден в $PROJECT_ROOT"
    echo "💡 Убедитесь, что проект находится в ~/Documents/atra-web-ide"
    exit 1
fi

# Запуск скрипта
cd "$PROJECT_ROOT"
python3 scripts/victoria_chat.py "$@"
