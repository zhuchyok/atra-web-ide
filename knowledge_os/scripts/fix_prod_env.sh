#!/bin/bash
# Скрипт для автоматического исправления PROD окружения на сервере

set -e

echo "🔧 Исправление PROD окружения на сервере..."

# Путь к проекту (настройте под ваш сервер)
PROJECT_DIR="${1:-/root/atra}"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Директория проекта не найдена: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"

# Проверяем текущее окружение
CURRENT_ENV=$(grep "^ATRA_ENV=" env | cut -d'=' -f2 || echo "dev")
echo "📊 Текущее окружение: $CURRENT_ENV"

if [ "$CURRENT_ENV" = "prod" ]; then
    echo "✅ Окружение уже установлено в PROD"
else
    echo "🔧 Устанавливаю ATRA_ENV=prod..."
    sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env
    echo "✅ Окружение изменено на PROD"
fi

# Проверяем токены
if grep -q "TELEGRAM_TOKEN=" env && grep -q "TELEGRAM_TOKEN_DEV=" env; then
    echo "✅ Токены настроены"
else
    echo "⚠️  Проверьте токены в env файле"
fi

# Проверяем chat_ids
if grep -q "TELEGRAM_CHAT_IDS=" env; then
    CHAT_IDS=$(grep "^TELEGRAM_CHAT_IDS=" env | cut -d'=' -f2)
    if [ -n "$CHAT_IDS" ] && [ "$CHAT_IDS" != "958930260,556251171" ]; then
        echo "✅ Chat IDs настроены"
    else
        echo "⚠️  Установите реальные Chat IDs в env файле"
    fi
else
    echo "⚠️  TELEGRAM_CHAT_IDS не найден в env файле"
fi

# Перезапускаем систему (если используется systemd)
if systemctl is-active --quiet atra 2>/dev/null; then
    echo "🔄 Перезапускаю систему..."
    systemctl restart atra
    sleep 2
    if systemctl is-active --quiet atra; then
        echo "✅ Система перезапущена"
    else
        echo "⚠️  Система не запустилась, проверьте логи: systemctl status atra"
    fi
elif [ -f "start_continuous.sh" ]; then
    echo "🔄 Перезапускаю через start_continuous.sh..."
    ./stop_continuous.sh 2>/dev/null || true
    sleep 2
    nohup ./start_continuous.sh > /dev/null 2>&1 &
    echo "✅ Система перезапущена"
else
    echo "⚠️  Не найден способ перезапуска, перезапустите вручную"
fi

# Финальная проверка
echo ""
echo "📊 Финальная проверка:"
grep "^ATRA_ENV=" env
echo ""
echo "✅ Готово! Проверьте логи: tail -f logs/system.log"
