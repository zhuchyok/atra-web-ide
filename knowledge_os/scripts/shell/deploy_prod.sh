#!/bin/bash
# Скрипт для обновления и перезапуска на PROD сервере

SERVER="185.177.216.15"
SERVER_USER="root"
SERVER_PATH="/root/atra"

echo "🚀 ОБНОВЛЕНИЕ И ПЕРЕЗАПУСК НА PROD СЕРВЕРЕ"
echo "=========================================="
echo ""

# 1. Локально: Остановка процессов
echo "📋 Шаг 1: Остановка локальных процессов..."
LOCAL_PIDS=$(ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | awk '{print $2}' 2>/dev/null || echo "")

if [ -n "$LOCAL_PIDS" ]; then
    echo "   Найдены процессы: $LOCAL_PIDS"
    for pid in $LOCAL_PIDS; do
        kill -9 $pid 2>/dev/null || true
    done
    sleep 1
    echo "   ✅ Локальные процессы остановлены"
else
    echo "   ✅ Локальные процессы не запущены"
fi

# 2. Git commit и push
echo ""
echo "📋 Шаг 2: Commit и push изменений..."
cd /Users/zhuchyok/Documents/GITHUB/atra/atra

# Добавляем файлы
git add signal_live.py docs/SIGNAL_*.md check_*.py find_*.py deploy_*.sh QUICK_DEPLOY_COMMANDS.txt 2>/dev/null || true

# Commit
if [ -n "$(git status --porcelain)" ]; then
    git commit -m "Добавлено сохранение сигналов в БД при отправке + диагностика" 2>&1
    echo "   ✅ Изменения закоммичены"
else
    echo "   ℹ️ Нет изменений для коммита"
fi

# Push
git push origin insight 2>&1
echo "   ✅ Push выполнен"

# 3. Инструкции для сервера
echo ""
echo "=========================================="
echo "📋 СЛЕДУЮЩИЕ ШАГИ (выполнить на сервере):"
echo "=========================================="
echo ""
echo "1. Подключитесь к серверу:"
echo "   ssh $SERVER_USER@$SERVER"
echo "   Пароль: u44Ww9NmtQj,XG"
echo ""
echo "2. Выполните команды:"
echo "   cd $SERVER_PATH"
echo "   git fetch origin"
echo "   git checkout insight"
echo "   git pull origin insight"
echo ""
echo "3. Остановите старые процессы:"
echo "   pkill -f 'python.*signal_live' || true"
echo "   pkill -f 'python.*main.py' || true"
echo "   sleep 2"
echo "   ps aux | grep -E '(python.*signal_live|python.*main\.py)' | grep -v grep | awk '{print \$2}' | xargs kill -9 2>/dev/null || true"
echo ""
echo "4. Запустите процесс:"
echo "   nohup python3 main.py > main.log 2>&1 &"
echo "   sleep 3"
echo ""
echo "5. Проверьте:"
echo "   ps aux | grep 'python.*main.py' | grep -v grep"
echo "   tail -20 main.log"
echo ""
echo "=========================================="
echo "✅ Локальные шаги завершены!"
echo "Теперь подключитесь к серверу и выполните команды выше."
