#!/bin/bash
# Запуск интерактивного чата с Victoria в терминале (полная версия: /project, /health, /status)
# Использование: bash scripts/chat_victoria.sh
# Или из любой директории: bash ~/Documents/atra-web-ide/scripts/chat_victoria.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f "scripts/victoria_chat_standalone.py" ]; then
    exec python3 scripts/victoria_chat_standalone.py "$@"
elif [ -f "scripts/victoria_chat.py" ]; then
    exec python3 scripts/victoria_chat.py "$@"
else
    echo "❌ Ни victoria_chat_standalone.py, ни victoria_chat.py не найдены в $ROOT/scripts"
    exit 1
fi
