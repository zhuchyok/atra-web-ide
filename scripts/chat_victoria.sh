#!/bin/bash
# Запуск интерактивного чата с Victoria в терминале
# Использование: bash scripts/chat_victoria.sh
# Или из любой директории: bash ~/Documents/atra-web-ide/scripts/chat_victoria.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f "scripts/victoria_chat.py" ]; then
    echo "❌ scripts/victoria_chat.py не найден в $ROOT"
    exit 1
fi

exec python3 scripts/victoria_chat.py "$@"
