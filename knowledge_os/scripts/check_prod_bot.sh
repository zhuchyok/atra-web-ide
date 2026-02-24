#!/bin/bash
# Скрипт для проверки и перезапуска бота на прод-сервере

SERVER="root@185.177.216.15"
SERVER_PATH="/root/atra"

echo "🔍 ПРОВЕРКА СОСТОЯНИЯ БОТА НА ПРОД-СЕРВЕРЕ"
echo "=========================================="
echo ""

# Функция для выполнения команд на сервере
run_remote() {
    sshpass -p 'u44Ww9NmtQj,XG' ssh -o StrictHostKeyChecking=no "$SERVER" "$1"
}

echo "1️⃣ Проверка процессов main.py:"
echo "-------------------------------"
run_remote "cd $SERVER_PATH && ps aux | grep main.py | grep -v grep"
PROCESS_COUNT=$(run_remote "cd $SERVER_PATH && ps aux | grep main.py | grep -v grep | wc -l")
echo "Количество процессов: $PROCESS_COUNT"
echo ""

echo "2️⃣ Проверка последних логов (ошибки):"
echo "--------------------------------------"
run_remote "cd $SERVER_PATH && tail -30 system_improved.log | grep -E 'ERROR|Exception|Failed|Traceback' | tail -10"
echo ""

echo "3️⃣ Проверка Telegram polling:"
echo "-----------------------------"
run_remote "cd $SERVER_PATH && tail -20 system_improved.log | grep -E 'Polling|Bot authorized|ERROR.*TG|telegram' | tail -5"
echo ""

echo "4️⃣ Проверка блокировок:"
echo "----------------------"
run_remote "cd $SERVER_PATH && ls -la *.lock 2>/dev/null || echo 'Блокировок нет'"
echo ""

echo "5️⃣ Проверка активности за последний час:"
echo "----------------------------------------"
run_remote "cd $SERVER_PATH && python3 -c \"
import sqlite3
try:
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\\\"now\\\", \\\"-1 hours\\\")')
    count = cursor.fetchone()[0]
    print(f'Циклов за последний час: {count}')
    conn.close()
except Exception as e:
    print(f'Ошибка проверки: {e}')
\""
echo ""

echo "6️⃣ Проверка переменных окружения:"
echo "----------------------------------"
run_remote "cd $SERVER_PATH && echo \"ATRA_ENV: \$(echo \$ATRA_ENV)\" && echo \"TELEGRAM_TOKEN: \$(grep TELEGRAM_TOKEN env 2>/dev/null | head -1 | cut -d'=' -f2 | cut -c1-20)...\""
echo ""

# Определяем, нужно ли перезапускать
if [ "$PROCESS_COUNT" -eq 0 ]; then
    echo "❌ БОТ НЕ ЗАПУЩЕН! Требуется запуск."
    echo ""
    echo "🚀 ЗАПУСК БОТА..."
    run_remote "cd $SERVER_PATH && export ATRA_ENV=prod && nohup python3 main.py > server.log 2>&1 &"
    sleep 3
    echo "✅ Бот запущен"
elif [ "$PROCESS_COUNT" -gt 1 ]; then
    echo "⚠️ МНОЖЕСТВЕННЫЕ ЭКЗЕМПЛЯРЫ! Требуется перезапуск."
    echo ""
    echo "🔄 ПЕРЕЗАПУСК БОТА..."
    run_remote "cd $SERVER_PATH && pkill -9 -f main.py && sleep 2 && rm -f *.lock && export ATRA_ENV=prod && nohup python3 main.py > server.log 2>&1 &"
    sleep 3
    echo "✅ Бот перезапущен"
else
    echo "✅ Процесс запущен (1 экземпляр)"
    echo ""
    echo "📋 Последние 10 строк логов:"
    run_remote "cd $SERVER_PATH && tail -10 system_improved.log"
fi

echo ""
echo "7️⃣ Финальная проверка:"
echo "----------------------"
run_remote "cd $SERVER_PATH && ps aux | grep main.py | grep -v grep"
echo ""
echo "📋 Последние строки server.log:"
run_remote "cd $SERVER_PATH && tail -15 server.log 2>/dev/null || tail -15 system_improved.log"
