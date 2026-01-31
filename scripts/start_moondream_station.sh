#!/bin/bash
# Скрипт запуска Moondream Station (Moondream 3 Preview с MLX)
# Работает на порту 2020 по умолчанию

set -e

echo "🚀 Запуск Moondream Station (Moondream 3 Preview с MLX)..."
echo "📡 API будет доступен на: http://localhost:2020"
echo ""

# Проверяем, установлен ли moondream-station
if ! command -v moondream-station &> /dev/null; then
    echo "❌ moondream-station не найден!"
    echo "💡 Установите: pip install moondream-station"
    exit 1
fi

# Запускаем Moondream Station
# По умолчанию работает на порту 2020
moondream-station
