#!/bin/bash

# Простой мониторинг для сервера
# Не требует дополнительных файлов

echo "🔍 МОНИТОРИНГ СЕРВЕРА ATRA"
echo "=========================="

# Проверяем процессы main.py
echo "🔄 Процессы main.py:"
MAIN_PROCESSES=$(ps aux | grep main.py | grep -v grep)
if [ -n "$MAIN_PROCESSES" ]; then
    echo "✅ Бот запущен:"
    echo "$MAIN_PROCESSES"
else
    echo "❌ Бот не запущен"
fi

echo ""
echo "💻 Использование ресурсов:"
echo "CPU: $(top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1)%"
echo "RAM: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"

echo ""
echo "📝 Последние логи:"
if [ -f "system_improved.log" ]; then
    echo "Последние 5 строк из system_improved.log:"
    tail -n 5 system_improved.log
else
    echo "Лог файл system_improved.log не найден"
fi

echo ""
echo "🔄 Непрерывный мониторинг (Ctrl+C для выхода):"
echo "=============================================="

# Простой цикл мониторинга
while true; do
    clear
    echo "🔍 МОНИТОРИНГ СЕРВЕРА ATRA - $(date)"
    echo "====================================="
    
    # Процессы
    echo "🔄 Процессы main.py:"
    MAIN_PROCESSES=$(ps aux | grep main.py | grep -v grep)
    if [ -n "$MAIN_PROCESSES" ]; then
        echo "✅ Бот работает:"
        echo "$MAIN_PROCESSES"
    else
        echo "❌ Бот не запущен"
    fi
    
    echo ""
    echo "💻 Ресурсы:"
    echo "CPU: $(top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1)%"
    echo "RAM: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
    
    echo ""
    echo "📝 Последние логи:"
    if [ -f "system_improved.log" ]; then
        tail -n 3 system_improved.log
    else
        echo "Лог файл не найден"
    fi
    
    echo ""
    echo "Обновление через 10 секунд... (Ctrl+C для выхода)"
    sleep 10
done
