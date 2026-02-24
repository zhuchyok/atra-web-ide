#!/bin/bash
# Полный скрипт развертывания - выполнить на сервере вручную

set -e

echo "🚀 ПОЛНОЕ РАЗВЕРТЫВАНИЕ НА PROD СЕРВЕРЕ"
echo "========================================"

cd /root/atra

echo ""
echo "📥 Шаг 1: Обновление кода..."
git fetch origin
git checkout insight
git pull origin insight
echo "✅ Код обновлен"

echo ""
echo "🛑 Шаг 2: Остановка всех процессов..."
# Останавливаем все процессы
pkill -f "python.*signal_live" || true
pkill -f "python.*main.py" || true
sleep 2

# Принудительная остановка
REMAINING=$(ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "   Принудительная остановка оставшихся процессов..."
    ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Финальная проверка
FINAL_CHECK=$(ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | wc -l)
if [ "$FINAL_CHECK" -eq 0 ]; then
    echo "✅ Все процессы остановлены"
else
    echo "⚠️ Остались процессы (проверьте вручную):"
    ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep
fi

echo ""
echo "🔍 Шаг 3: Проверка окружения..."
ATRA_ENV=$(python3 -c "from config import ATRA_ENV; print(ATRA_ENV)" 2>/dev/null || echo "unknown")
echo "   ATRA_ENV: $ATRA_ENV"

if [ "$ATRA_ENV" != "prod" ]; then
    echo "   ⚠️ ВНИМАНИЕ: ATRA_ENV = $ATRA_ENV (ожидается prod)"
    echo "   Проверьте файл env или установите: export ATRA_ENV=prod"
fi

echo ""
echo "🚀 Шаг 4: Запуск процесса..."
nohup python3 main.py > main.log 2>&1 &
NEW_PID=$!
sleep 3

# Проверка запуска
if ps -p $NEW_PID > /dev/null 2>&1; then
    echo "✅ Процесс запущен: PID $NEW_PID"
else
    echo "❌ Процесс не запустился! Проверьте логи:"
    tail -30 main.log
    exit 1
fi

echo ""
echo "📊 Шаг 5: Статус процессов:"
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep || echo "   Процессы не найдены"

echo ""
echo "📋 Шаг 6: Последние строки лога:"
tail -20 main.log

echo ""
echo "========================================"
echo "✅ РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО"
echo "========================================"
echo ""
echo "Мониторинг логов: tail -f main.log"
echo "Проверка процесса: ps aux | grep main.py"
