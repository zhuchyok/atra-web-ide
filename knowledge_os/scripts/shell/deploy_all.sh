#!/bin/bash
# Полный автоматический скрипт развертывания

set -e

SERVER="185.177.216.15"
USER="root"
PASSWORD="u44Ww9NmtQj,XG"

echo "🚀 АВТОМАТИЧЕСКОЕ РАЗВЕРТЫВАНИЕ НА PROD СЕРВЕРЕ"
echo "================================================"

# Проверка наличия sshpass
if ! command -v sshpass &> /dev/null; then
    echo "⚠️ sshpass не установлен. Устанавливаю..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install hudochenkov/sshpass/sshpass 2>/dev/null || echo "Не удалось установить sshpass через brew"
        else
            echo "Установите sshpass вручную: brew install hudochenkov/sshpass/sshpass"
        fi
    fi
fi

# Если sshpass доступен, используем его
if command -v sshpass &> /dev/null; then
    echo "✅ Используется sshpass для автоматического ввода пароля"
    SSHPASS_CMD="sshpass -p '$PASSWORD'"
else
    echo "⚠️ sshpass недоступен. Потребуется ввод пароля вручную."
    SSHPASS_CMD=""
fi

echo ""
echo "📡 Подключение к серверу..."

# Выполнение команд на сервере
$SSHPASS_CMD ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 $USER@$SERVER << 'ENDSSH'
cd /root/atra

echo "📥 Обновление кода..."
git fetch origin
git checkout insight
git pull origin insight
echo "✅ Код обновлен"

echo ""
echo "🛑 Остановка всех процессов..."
pkill -f "python.*signal_live" || true
pkill -f "python.*main.py" || true
sleep 2
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
echo "✅ Процессы остановлены"

echo ""
echo "🔍 Проверка окружения..."
python3 -c "from config import ATRA_ENV; print(f'ATRA_ENV: {ATRA_ENV}')"

echo ""
echo "🚀 Запуск процесса..."
nohup python3 main.py > main.log 2>&1 &
sleep 3

echo ""
echo "📊 Проверка статуса:"
ps aux | grep "python.*main.py" | grep -v grep || echo "⚠️ Процесс не найден"

echo ""
echo "📋 Последние строки лога:"
tail -20 main.log

echo ""
echo "================================================"
echo "✅ РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО"
echo "================================================"
ENDSSH

echo ""
echo "✅ Все команды выполнены!"

