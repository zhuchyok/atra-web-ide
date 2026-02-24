#!/bin/bash
# Ручной скрипт для обновления на сервере (выполнять на сервере)

set -e

echo "🚀 ОБНОВЛЕНИЕ И ПЕРЕЗАПУСК НА PROD СЕРВЕРЕ"
echo "=========================================="

cd /root/atra

echo ""
echo "📥 Шаг 1: Обновление кода с git..."
git fetch origin
git checkout insight
git pull origin insight

echo ""
echo "🛑 Шаг 2: Остановка старых процессов..."
# Останавливаем все процессы Python связанные с atra
pkill -f "python.*signal_live" || true
pkill -f "python.*main.py" || true
sleep 2

# Проверяем, что процессы остановлены
REMAINING=$(ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "   ⚠️ Некоторые процессы еще работают, принудительная остановка..."
    ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
    sleep 2
fi

echo "   ✅ Старые процессы остановлены"

echo ""
echo "🔍 Шаг 3: Проверка окружения..."
ATRA_ENV=$(python3 -c "from config import ATRA_ENV; print(ATRA_ENV)" 2>/dev/null || echo "unknown")
echo "   ATRA_ENV: $ATRA_ENV"

if [ "$ATRA_ENV" != "prod" ]; then
    echo "   ⚠️ ВНИМАНИЕ: ATRA_ENV = $ATRA_ENV (ожидается prod)"
    echo "   Проверьте файл env или установите: export ATRA_ENV=prod"
fi

echo ""
echo "🚀 Шаг 4: Запуск процесса в PROD режиме..."
nohup python3 main.py > main.log 2>&1 &
sleep 3

# Проверяем, что процесс запустился
NEW_PID=$(ps aux | grep -E "python.*main\.py" | grep -v grep | awk '{print $2}' | head -1)
if [ -n "$NEW_PID" ]; then
    echo "   ✅ Процесс запущен: PID $NEW_PID"
else
    echo "   ❌ Процесс не запустился! Проверьте логи:"
    tail -20 main.log 2>/dev/null || echo "   Логи недоступны"
    exit 1
fi

echo ""
echo "📊 Шаг 5: Статус процессов:"
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep || echo "   Процессы не найдены"

echo ""
echo "✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО"
echo "Проверьте логи: tail -f main.log"
