# 🔍 ПРОВЕРКА СТАТУСА СЕРВЕРА

## 🔗 Подключение к серверу:

```bash
ssh root@185.177.216.15
# Пароль: u44Ww9NmtQj,XG
```

## 📋 КОМАНДЫ ДЛЯ ПРОВЕРКИ (копировать на сервер):

### 1️⃣ Быстрая диагностика:

```bash
cd /root/atra
echo "=== СТАТУС СИСТЕМЫ ==="
echo "Процессы main.py:"
ps aux | grep main.py | grep -v grep | wc -l
ps aux | grep main.py | grep -v grep
echo ""
echo "Последние логи:"
tail -10 system_improved.log
```

### 2️⃣ Проверка Telegram бота:

```bash
cd /root/atra
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()

print('🔍 КОНФИГУРАЦИЯ СЕРВЕРА:')
print(f'ATRA_ENV: {os.getenv(\"ATRA_ENV\", \"не установлена\")}')
print(f'TELEGRAM_TOKEN (PROD): {os.getenv(\"TELEGRAM_TOKEN\", \"не установлен\")[:20]}...')
print(f'TELEGRAM_TOKEN_DEV: {os.getenv(\"TELEGRAM_TOKEN_DEV\", \"не установлен\")[:20]}...')
print(f'TELEGRAM_CHAT_IDS: {os.getenv(\"TELEGRAM_CHAT_IDS\", \"не установлены\")}')
"
```

### 3️⃣ Проверка процессов:

```bash
# Сколько экземпляров
ps aux | grep main.py | grep -v grep | wc -l

# Подробная информация
ps aux | grep main.py | grep -v grep

# Проверка блокировок
ls -la atra.lock 2>/dev/null && echo "⚠️ Файл блокировки найден!" || echo "✅ Блокировок нет"
```

### 4️⃣ Проверка логов на ошибки:

```bash
# Ошибки в логах
grep -E "ERROR|Exception|Failed" system_improved.log | tail -20

# Проверка Telegram polling
grep "Polling\|Bot authorized\|ERROR.*TG" system_improved.log | tail -10

# Последние сигналы
grep "callback_build" system_improved.log | tail -5
```

### 5️⃣ Проверка активности системы:

```bash
cd /root/atra
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()

print('🔍 АКТИВНОСТЬ ЗА ПОСЛЕДНИЕ 24 ЧАСА:')

# Циклы проверки
cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\"now\", \"-24 hours\")')
print(f'Циклов проверки: {cursor.fetchone()[0]}')

# API запросы
cursor.execute('SELECT COUNT(*) FROM telemetry_api WHERE datetime(ts) >= datetime(\"now\", \"-24 hours\")')
print(f'API запросов: {cursor.fetchone()[0]}')

# Сигналы
cursor.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) >= datetime(\"now\", \"-24 hours\")')
print(f'Сигналов сгенерировано: {cursor.fetchone()[0]}')

# Последний сигнал
cursor.execute('SELECT symbol, side, datetime(ts, \"localtime\") FROM signals ORDER BY ts DESC LIMIT 1')
last = cursor.fetchone()
if last:
    print(f'Последний сигнал: {last[0]} {last[1]} в {last[2]}')

conn.close()
"
```

### 6️⃣ Проверка почему нет сигналов:

```bash
# Проверяем логи на наличие кандидатов
grep -c "candidate" system_improved.log
echo "Кандидатов найдено: ^"

# Проверяем причины отклонения
grep -c "gate_trend_skip" system_improved.log
echo "Отклонено по тренду: ^"

grep -c "gate_mtf_skip" system_improved.log
echo "Отклонено по MTF: ^"

grep -c "открытую позицию" system_improved.log
echo "Заблокировано открытыми позициями: ^"

grep -c "callback_build" system_improved.log
echo "Отправлено сигналов: ^"
```

### 7️⃣ Если бот не работает - перезапуск:

```bash
cd /root/atra

# Остановить все процессы
pkill -9 -f main.py
sleep 2

# Очистить блокировки
rm -f atra.lock telegram_*.lock .telegram_*

# Запустить
nohup python3 main.py > server.log 2>&1 &
sleep 3

# Проверить
ps aux | grep main.py | grep -v grep
echo ""
echo "Логи:"
tail -20 server.log
```

### 8️⃣ Мониторинг в реальном времени:

```bash
# Логи
tail -f system_improved.log

# Или мониторинг с фильтром
tail -f system_improved.log | grep -E "(callback_build|ERROR|WARNING)"
```

## 🎯 ВОЗМОЖНЫЕ ПРОБЛЕМЫ НА СЕРВЕРЕ:

### A. Множественные экземпляры

```bash
# Проверить
ps aux | grep main.py | grep -v grep | wc -l

# Должно быть: 1
# Если больше - остановить все и запустить заново
```

### B. Блокировка Telegram polling

```bash
# Проверить в логах
grep "Поллинг уже запущен\|ERROR.*TG" system_improved.log | tail -5
```

### C. Неправильная среда (DEV вместо PROD)

```bash
# Проверить
echo $ATRA_ENV

# Должно быть: prod
# Если нет - установить:
export ATRA_ENV=prod
```

### D. Система не запущена

```bash
# Проверить телеметрию
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\"now\", \"-1 hours\")')
print(f'Циклов за последний час: {cursor.fetchone()[0]}')
conn.close()
"

# Если 0 - система не работает!
```

## 🚀 БЫСТРОЕ ИСПРАВЛЕНИЕ:

Скопируйте эти команды на сервер одной строкой:

```bash
cd /root/atra && pkill -9 -f main.py && sleep 2 && rm -f *.lock && export ATRA_ENV=prod && nohup python3 main.py > server.log 2>&1 & sleep 3 && ps aux | grep main.py | grep -v grep && tail -20 server.log
```

---

## 📝 ПОСЛЕ ПОДКЛЮЧЕНИЯ К СЕРВЕРУ:

**Выполните команды из раздела 1-4 и пришлите мне результаты!**
