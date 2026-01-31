#!/bin/bash
echo "🛑 Остановка ATRA..."

# Находим и останавливаем процессы
pkill -f "python3 main.py" 2>/dev/null
pkill -f "atra" 2>/dev/null

# Удаляем lock файлы
rm -f atra.lock

echo "✅ ATRA остановлен!"
