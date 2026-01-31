#!/bin/bash
# Скрипт запуска ATRA для сервера

echo "🚀 Запуск системы ATRA на сервере..."

# Устанавливаем переменные окружения
export PYTHONPATH="/Users/zhuchyok/Library/Python/3.9/lib/python/site-packages:$PYTHONPATH"
export PYTHONPATH="/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/site-packages:$PYTHONPATH"
export PYTHONPATH="/Library/Frameworks/Python.framework/Versions/3.9/lib/python3.9/site-packages:$PYTHONPATH"
export PYTHONPATH="/usr/local/lib/python3.9/site-packages:$PYTHONPATH"
export PYTHONPATH="/usr/lib/python3.9/site-packages:$PYTHONPATH"

# Проверяем и останавливаем существующие процессы
echo "🔍 Проверка существующих процессов..."
python3 check_processes.py <<< "y" 2>/dev/null || true

# Ждем завершения процессов
sleep 3

# Запускаем систему
echo "🚀 Запуск системы..."
python3 main.py

echo "✅ Система запущена"
