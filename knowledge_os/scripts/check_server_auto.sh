#!/bin/bash

# Автоматическая проверка сервера
SERVER="root@185.177.216.15"
PASSWORD="u44Ww9NmtQj,XG"

echo "🔍 Автоматическая проверка сервера"
echo "=================================="

# Используем sshpass если доступен
if command -v sshpass &> /dev/null; then
    echo "✅ Используем sshpass"
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no $SERVER 'bash -s' << 'ENDSSH'
cd /root/atra

echo "=== СТАТУС СЕРВЕРА ==="
echo "Процессов main.py:"
ps aux | grep main.py | grep -v grep | wc -l

echo ""
echo "Процессы:"
ps aux | grep main.py | grep -v grep || echo "Нет процессов"

echo ""
echo "=== ПОСЛЕДНИЕ ЛОГИ ==="
tail -10 system_improved.log 2>/dev/null || echo "Лог не найден"

echo ""
echo "=== АКТИВНОСТЬ ==="
python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\"now\", \"-1 hours\")')
    cycles = cursor.fetchone()[0]
    print(f'Циклов за час: {cycles}')
    if cycles == 0:
        print('❌ СИСТЕМА НЕ РАБОТАЕТ!')
    cursor.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) >= datetime(\"now\", \"-24 hours\")')
    signals = cursor.fetchone()[0]
    print(f'Сигналов за 24ч: {signals}')
    conn.close()
except Exception as e:
    print(f'Ошибка: {e}')
" 2>/dev/null || echo "Не удалось проверить БД"

echo ""
echo "=== CALLBACK_BUILD ==="
grep -c "callback_build" system_improved.log 2>/dev/null || echo "0"

ENDSSH
else
    echo "❌ sshpass не установлен"
    echo "Попробуйте вручную:"
    echo "ssh $SERVER"
fi
