#!/bin/bash
# ВЫПОЛНИТЕ ЭТОТ СКРИПТ ДЛЯ АВТОМАТИЧЕСКОГО РАЗВЕРТЫВАНИЯ

SERVER="185.177.216.15"
USER="root"

echo "🚀 АВТОМАТИЧЕСКОЕ РАЗВЕРТЫВАНИЕ"
echo "================================"
echo ""
echo "Подключение к серверу: $USER@$SERVER"
echo "Пароль будет запрошен при подключении"
echo ""

ssh -o StrictHostKeyChecking=no $USER@$SERVER << 'ENDSSH'
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
echo "✅ РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО"
ENDSSH

echo ""
echo "✅ Готово!"

