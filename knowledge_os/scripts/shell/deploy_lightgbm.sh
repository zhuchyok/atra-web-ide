#!/bin/bash
# Скрипт для деплоя LightGBM системы на сервер

set -e

SERVER="185.177.216.15"
USER="root"
PASSWORD="u44Ww9NmtQj,XG"

echo "🚀 ДЕПЛОЙ LIGHTGBM СИСТЕМЫ НА СЕРВЕР"
echo "====================================="

# Проверка наличия sshpass
if ! command -v sshpass &> /dev/null; then
    echo "⚠️ sshpass не установлен. Устанавливаю..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install hudochenkov/sshpass/sshpass 2>/dev/null || echo "Не удалось установить sshpass"
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
echo "📦 Установка зависимостей LightGBM..."
echo "  - Установка libomp (требуется для LightGBM на macOS/Linux)..."
if command -v brew &> /dev/null; then
    brew install libomp 2>/dev/null || echo "⚠️ libomp уже установлен или недоступен через brew"
elif command -v apt-get &> /dev/null; then
    apt-get update -qq && apt-get install -y libomp-dev 2>/dev/null || echo "⚠️ libomp уже установлен"
elif command -v yum &> /dev/null; then
    yum install -y libomp-devel 2>/dev/null || echo "⚠️ libomp уже установлен"
else
    echo "⚠️ Менеджер пакетов не найден, пропускаем установку libomp"
fi

echo "  - Установка Python пакетов..."
export LDFLAGS="-L/opt/homebrew/opt/libomp/lib" 2>/dev/null || true
export CPPFLAGS="-I/opt/homebrew/opt/libomp/include" 2>/dev/null || true
python3 -m pip install --quiet --upgrade lightgbm scikit-learn || {
    echo "❌ Ошибка установки пакетов"
    exit 1
}
echo "✅ Зависимости установлены"

echo ""
echo "🎯 Обучение LightGBM моделей..."
export LDFLAGS="-L/opt/homebrew/opt/libomp/lib" 2>/dev/null || true
export CPPFLAGS="-I/opt/homebrew/opt/libomp/include" 2>/dev/null || true
python3 train_lightgbm_models.py || {
    echo "⚠️ Ошибка обучения моделей (возможно, недостаточно данных)"
    echo "   Система будет работать без ML фильтра до накопления данных"
}

echo ""
echo "🛑 Остановка текущих процессов..."
pkill -f "python.*signal_live" || true
pkill -f "python.*main.py" || true
sleep 2
ps aux | grep -E "(python.*signal_live|python.*main\.py)" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
echo "✅ Процессы остановлены"

echo ""
echo "🔍 Проверка окружения..."
python3 -c "from config import ATRA_ENV; print(f'ATRA_ENV: {ATRA_ENV}')" || echo "⚠️ Ошибка проверки окружения"

echo ""
echo "🚀 Запуск процесса с LightGBM..."
nohup python3 main.py > main.log 2>&1 &
sleep 5

echo ""
echo "📊 Проверка статуса:"
ps aux | grep "python.*main.py" | grep -v grep || echo "⚠️ Процесс не найден"

echo ""
echo "📋 Последние строки лога (проверка LightGBM):"
tail -30 main.log | grep -E "(LightGBM|lightgbm|ML|переобучение)" || echo "ℹ️ Логи LightGBM пока не появились"

echo ""
echo "================================================"
echo "✅ ДЕПЛОЙ LIGHTGBM ЗАВЕРШЕН"
echo "================================================"
ENDSSH

echo ""
echo "✅ Все команды выполнены!"
