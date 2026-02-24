#!/bin/bash
# Скрипт для обновления и перезапуска на PROD сервере

set -e

SERVER="185.177.216.15"
SERVER_USER="root"
SERVER_PASS="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🚀 ОБНОВЛЕНИЕ И ПЕРЕЗАПУСК НА PROD СЕРВЕРЕ"
echo "=" | head -c 80 && echo ""

# 1. Остановка локальных процессов
echo "📋 Шаг 1: Остановка локальных процессов..."
LOCAL_PIDS=$(ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | awk '{print $2}')

if [ -n "$LOCAL_PIDS" ]; then
    echo "   Найдены локальные процессы: $LOCAL_PIDS"
    for pid in $LOCAL_PIDS; do
        echo "   Останавливаем процесс $pid..."
        kill -9 $pid 2>/dev/null || true
    done
    sleep 2
    echo "   ✅ Локальные процессы остановлены"
else
    echo "   ✅ Локальные процессы не запущены"
fi

# 2. Commit изменений (если есть)
echo ""
echo "📋 Шаг 2: Проверка изменений в git..."
if [ -n "$(git status --porcelain)" ]; then
    echo "   Найдены изменения, делаем commit..."
    git add signal_live.py check_signals_after_753.py find_all_signal_storage.py check_why_no_signals_today.py check_where_to_run.py docs/SIGNAL_*.md 2>/dev/null || true
    git commit -m "Добавлено сохранение сигналов в БД при отправке + диагностика" || true
    echo "   ✅ Изменения закоммичены"
else
    echo "   ✅ Нет изменений для коммита"
fi

# 3. Push в git
echo ""
echo "📋 Шаг 3: Push в git..."
git push origin insight 2>&1 || echo "   ⚠️ Не удалось сделать push (возможно, уже запушено)"

# 4. Подключение к серверу и обновление
echo ""
echo "📋 Шаг 4: Подключение к серверу и обновление..."
echo "   Сервер: $SERVER_USER@$SERVER"
echo "   Путь: $SERVER_PATH"

# Используем sshpass для автоматического ввода пароля
sshpass -p "$SERVER_PASS" ssh -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER" << 'ENDSSH'
    set -e
    cd /root/atra

    echo "   📥 Обновление кода с git..."
    git fetch origin
    git checkout insight
    git pull origin insight

    echo "   🛑 Остановка старых процессов..."
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

    echo "   🔍 Проверка окружения..."
    ATRA_ENV=$(python3 -c "from config import ATRA_ENV; print(ATRA_ENV)" 2>/dev/null || echo "unknown")
    echo "   ATRA_ENV: $ATRA_ENV"

    if [ "$ATRA_ENV" != "prod" ]; then
        echo "   ⚠️ ВНИМАНИЕ: ATRA_ENV = $ATRA_ENV (ожидается prod)"
        echo "   Проверьте файл env или переменную окружения ATRA_ENV"
    fi

    echo "   🚀 Запуск процесса в PROD режиме..."
    nohup python3 main.py > main.log 2>&1 &
    sleep 3

    # Проверяем, что процесс запустился
    NEW_PID=$(ps aux | grep -E "python.*main\.py" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$NEW_PID" ]; then
        echo "   ✅ Процесс запущен: PID $NEW_PID"
    else
        echo "   ❌ Процесс не запустился! Проверьте логи:"
        tail -20 main.log 2>/dev/null || echo "   Логи недоступны"
    fi

    echo "   📊 Статус процессов:"
    ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep || echo "   Процессы не найдены"
ENDSSH

echo ""
echo "✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО"
echo "=" | head -c 80 && echo ""
echo "Проверьте логи на сервере:"
echo "  ssh $SERVER_USER@$SERVER 'tail -f $SERVER_PATH/main.log'"
