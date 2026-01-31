#!/bin/bash
echo "🚀 Запуск ATRA Trading Bot..."

# Создаем необходимые директории
mkdir -p logs backups cache data models

# Проверяем Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден"
    exit 1
fi

# Проверяем зависимости
echo "📦 Проверка зависимостей..."
python3 -c "import pandas, numpy, ta, requests, aiohttp, httpx, telegram, aiofiles" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️ Некоторые зависимости отсутствуют. Устанавливаем основные..."
    pip3 install pandas>=1.5.0 numpy>=1.21.0 ta>=0.10.0 requests>=2.31.0 aiohttp>=3.13.2 httpx>=0.28.1 urllib3<2 python-telegram-bot>=22.5 aiofiles>=23.2.1
fi

# Запускаем основную систему
echo "🤖 Запуск торгового бота..."
python3 main.py

echo "✅ ATRA запущен!"
