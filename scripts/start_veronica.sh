#!/bin/bash

# Переходим в корень проекта
cd "$(dirname "$0")/.."

# Активируем venv
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ venv не найден. Сначала создайте его."
    exit 1
fi

# Установка необходимых зависимостей
echo "📦 Проверка зависимостей..."
pip install -q fastapi uvicorn pydantic httpx aiohttp duckduckgo-search

# Запуск сервера
echo "🚀 Запуск Вероники (Bridge API) на порту 8000..."
python3 -m src.agents.bridge.server

