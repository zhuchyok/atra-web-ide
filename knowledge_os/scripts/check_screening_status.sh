#!/bin/bash
# Скрипт для проверки статуса скрининга

cd /Users/zhuchyok/Documents/GITHUB/atra/atra

echo "📊 СТАТУС СКРИНИНГА:"
echo ""

# Проверка процесса
PROCESS=$(ps aux | grep "mass_screening_by_correlation_groups" | grep -v grep)
if [ -n "$PROCESS" ]; then
    PID=$(echo $PROCESS | awk '{print $2}')
    CPU=$(echo $PROCESS | awk '{print $3}')
    MEM=$(echo $PROCESS | awk '{print $4}')
    echo "✅ Процесс работает (PID: $PID, CPU: $CPU%, MEM: $MEM%)"
else
    echo "❌ Процесс не найден"
fi

echo ""
echo "📁 Последние результаты:"
ls -lt data/reports/correlation_groups_* 2>/dev/null | head -2 | awk '{print "   "$9" ("$6" "$7" "$8")"}'

echo ""
echo "📊 Прогресс из лога:"
tail -20 logs/screening_fixed.log 2>/dev/null | grep -E "(Тестируем группу|\[.*/.*\] Тестируем|✅.*сделок|Группа.*прошли)" | tail -5

echo ""
echo "⏱️ Время работы:"
if [ -n "$PID" ]; then
    ps -p $PID -o etime= 2>/dev/null | awk '{print "   "$0}'
fi

