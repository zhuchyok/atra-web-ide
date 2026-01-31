#!/bin/bash
# Скрипт для автоматического исправления PROD окружения на удаленном сервере

SERVER="root@185.177.216.15"
PROJECT_DIR="/root/atra"  # Настройте под ваш путь

echo "🔧 Подключение к серверу и исправление PROD окружения..."

ssh $SERVER << 'ENDSSH'
set -e

cd /root/atra || { echo "❌ Директория не найдена"; exit 1; }

echo "📊 Текущее окружение:"
grep "^ATRA_ENV=" env || echo "ATRA_ENV не найден"

echo "🔧 Устанавливаю ATRA_ENV=prod..."
sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env

echo "✅ Проверка изменений:"
grep "^ATRA_ENV=" env

echo "🔄 Перезапускаю систему..."
if systemctl is-active --quiet atra 2>/dev/null; then
    systemctl restart atra
    sleep 2
    systemctl status atra --no-pager -l || true
elif [ -f "stop_continuous.sh" ] && [ -f "start_continuous.sh" ]; then
    ./stop_continuous.sh 2>/dev/null || true
    sleep 2
    nohup ./start_continuous.sh > /dev/null 2>&1 &
    echo "✅ Система перезапущена через скрипты"
else
    echo "⚠️  Перезапустите систему вручную"
fi

echo ""
echo "✅ Готово! Проверьте логи: tail -f logs/system.log"
ENDSSH

echo "✅ Исправление завершено на сервере"

