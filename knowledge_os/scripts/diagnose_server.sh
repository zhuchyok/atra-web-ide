#!/bin/bash

# Скрипт диагностики сервера
# Выполнять на сервере: cd /root/atra && ./diagnose_server.sh

echo "🔍 ДИАГНОСТИКА СЕРВЕРА ATRA"
echo "============================================================"

# 1. Проверка процессов
echo ""
echo "1️⃣ ПРОЦЕССЫ:"
PROCESS_COUNT=$(ps aux | grep main.py | grep -v grep | wc -l)
echo "   Запущено процессов main.py: $PROCESS_COUNT"

if [ $PROCESS_COUNT -eq 0 ]; then
    echo "   ❌ БОТ НЕ ЗАПУЩЕН!"
elif [ $PROCESS_COUNT -eq 1 ]; then
    echo "   ✅ Один процесс (норма)"
    ps aux | grep main.py | grep -v grep
else
    echo "   ⚠️  МНОЖЕСТВЕННЫЕ ЭКЗЕМПЛЯРЫ! (конфликт)"
    ps aux | grep main.py | grep -v grep
fi

# 2. Проверка окружения
echo ""
echo "2️⃣ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ:"
echo "   ATRA_ENV: ${ATRA_ENV:-не установлена}"

if [ -f ".env" ]; then
    echo "   ✅ Файл .env найден"
    echo "   Содержимое:"
    grep -E "TELEGRAM_TOKEN|ATRA_ENV|CHAT_IDS" .env 2>/dev/null | sed 's/=.*$/=***/' || echo "   Не удалось прочитать"
else
    echo "   ❌ Файл .env не найден!"
fi

# 3. Проверка блокировок
echo ""
echo "3️⃣ БЛОКИРОВКИ:"
if [ -f "atra.lock" ]; then
    echo "   ⚠️  Найден файл atra.lock"
else
    echo "   ✅ Блокировок нет"
fi

# 4. Проверка логов
echo ""
echo "4️⃣ ПОСЛЕДНИЕ ЛОГИ:"
if [ -f "system_improved.log" ]; then
    echo "   Последние 5 строк:"
    tail -5 system_improved.log
else
    echo "   ❌ Файл system_improved.log не найден"
fi

# 5. Проверка активности БД
echo ""
echo "5️⃣ АКТИВНОСТЬ СИСТЕМЫ (последний час):"
python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('trading.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\"now\", \"-1 hours\")')
    cycles = cursor.fetchone()[0]
    print(f'   Циклов проверки: {cycles}')
    
    if cycles == 0:
        print('   ❌ СИСТЕМА НЕ РАБОТАЕТ!')
    else:
        print('   ✅ Система активна')
    
    cursor.execute('SELECT symbol, side, datetime(ts, \"localtime\") FROM signals ORDER BY ts DESC LIMIT 1')
    last = cursor.fetchone()
    if last:
        print(f'   Последний сигнал: {last[0]} {last[1]} в {last[2]}')
    
    conn.close()
except Exception as e:
    print(f'   ❌ Ошибка БД: {e}')
" 2>/dev/null || echo "   ❌ Не удалось проверить БД"

# 6. Проверка ошибок
echo ""
echo "6️⃣ ОШИБКИ В ЛОГАХ:"
if [ -f "system_improved.log" ]; then
    ERROR_COUNT=$(grep -c "ERROR" system_improved.log 2>/dev/null || echo "0")
    echo "   Ошибок найдено: $ERROR_COUNT"
    
    if [ $ERROR_COUNT -gt 0 ]; then
        echo "   Последние 3 ошибки:"
        grep "ERROR" system_improved.log | tail -3
    fi
else
    echo "   ⚠️  Лог файл не найден"
fi

# 7. Проверка Telegram
echo ""
echo "7️⃣ TELEGRAM БОТ:"
grep "Bot authorized\|Polling запущен\|ERROR.*telegram" system_improved.log 2>/dev/null | tail -3 || echo "   ⚠️  Нет информации о Telegram боте"

# 8. Проверка сигналов за сегодня
echo ""
echo "8️⃣ СИГНАЛЫ ЗА СЕГОДНЯ:"
SIGNALS_TODAY=$(grep "callback_build" system_improved.log 2>/dev/null | grep "$(date +%Y-%m-%d)" | wc -l)
echo "   Отправлено сигналов: $SIGNALS_TODAY"

if [ $SIGNALS_TODAY -eq 0 ]; then
    echo "   ❌ СИГНАЛЫ НЕ ОТПРАВЛЯЮТСЯ!"
    
    # Проверяем кандидатов
    CANDIDATES=$(grep "candidate" system_improved.log 2>/dev/null | grep "$(date +%Y-%m-%d)" | wc -l)
    echo "   Кандидатов найдено: $CANDIDATES"
    
    TREND_OK=$(grep "trend_ok" system_improved.log 2>/dev/null | grep "$(date +%Y-%m-%d)" | wc -l)
    echo "   Прошли trend_ok: $TREND_OK"
fi

echo ""
echo "============================================================"
echo "💡 РЕЗЮМЕ:"

# Итоговая оценка
ISSUES=0

if [ $PROCESS_COUNT -eq 0 ]; then
    echo "❌ Бот не запущен - ЗАПУСТИТЕ!"
    ISSUES=$((ISSUES + 1))
elif [ $PROCESS_COUNT -gt 1 ]; then
    echo "⚠️  Множественные экземпляры - ПЕРЕЗАПУСТИТЕ!"
    ISSUES=$((ISSUES + 1))
fi

if [ -f "atra.lock" ]; then
    echo "⚠️  Есть блокировки - ОЧИСТИТЕ!"
    ISSUES=$((ISSUES + 1))
fi

if [ $SIGNALS_TODAY -eq 0 ]; then
    echo "❌ Сигналы не отправляются - ПРОВЕРЬТЕ ЛОГИКУ!"
    ISSUES=$((ISSUES + 1))
fi

if [ $ISSUES -eq 0 ]; then
    echo "✅ Все системы работают нормально!"
else
    echo ""
    echo "🔧 РЕКОМЕНДУЕМЫЕ ДЕЙСТВИЯ:"
    echo "   1. Остановите все процессы: pkill -9 -f main.py"
    echo "   2. Очистите блокировки: rm -f *.lock"
    echo "   3. Установите окружение: export ATRA_ENV=prod"
    echo "   4. Запустите: nohup python3 main.py > server.log 2>&1 &"
    echo "   5. Проверьте: ps aux | grep main.py"
fi

echo "============================================================"
