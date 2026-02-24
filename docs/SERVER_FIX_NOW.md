# 🚀 БЫСТРОЕ ИСПРАВЛЕНИЕ СЕРВЕРА

## 🔗 1. ПОДКЛЮЧИТЕСЬ К СЕРВЕРУ:

```bash
ssh root@185.177.216.15
```

Пароль: `u44Ww9NmtQj,XG`

---

## 📋 2. СКОПИРУЙТЕ И ВЫПОЛНИТЕ ЭТУ КОМАНДУ:

```bash
cd /root/atra && echo "=== ДИАГНОСТИКА ===" && echo "Процессов:" && ps aux | grep main.py | grep -v grep | wc -l && echo "" && echo "Последние логи:" && tail -5 system_improved.log && echo "" && echo "Сигналов за сегодня:" && grep -c "callback_build" system_improved.log | grep "$(date +%Y-%m-%d)" && echo "" && echo "Циклов за час:" && python3 -c "import sqlite3; conn = sqlite3.connect('trading.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\"now\", \"-1 hours\")'); print(cursor.fetchone()[0]); conn.close()" 2>/dev/null
```

---

## 🔧 3. ЕСЛИ СИСТЕМА НЕ РАБОТАЕТ:

### Полный перезапуск (скопируйте целиком):

```bash
cd /root/atra && \
echo "🛑 Останавливаем все процессы..." && \
pkill -9 -f main.py && \
sleep 2 && \
echo "🧹 Очищаем блокировки..." && \
rm -f *.lock telegram_*.lock .telegram_* && \
echo "🔧 Устанавливаем окружение..." && \
export ATRA_ENV=prod && \
echo "🚀 Запускаем бота..." && \
nohup python3 main.py > server.log 2>&1 & \
sleep 5 && \
echo "✅ Проверка..." && \
echo "Процессов:" && \
ps aux | grep main.py | grep -v grep | wc -l && \
echo "" && \
echo "Статус:" && \
ps aux | grep main.py | grep -v grep && \
echo "" && \
echo "Последние логи:" && \
tail -20 server.log
```

---

## 📊 4. ПОСЛЕ ЗАПУСКА - МОНИТОРИНГ:

```bash
# Смотреть логи в реальном времени
tail -f system_improved.log

# Или только сигналы
tail -f system_improved.log | grep callback_build
```

---

## 🎯 5. ПРОВЕРКА РЕЗУЛЬТАТА:

Через 5-10 минут выполните:

```bash
# Проверить активность
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\"now\", \"-10 minutes\")')
cycles = cursor.fetchone()[0]
print(f'✅ Циклов за 10 минут: {cycles}')
if cycles > 0:
    print('✅ СИСТЕМА РАБОТАЕТ!')
else:
    print('❌ СИСТЕМА НЕ РАБОТАЕТ!')
conn.close()
"

# Проверить сигналы
grep "callback_build" system_improved.log | tail -3
```

---

## ⚠️ ЧАСТЫЕ ПРОБЛЕМЫ:

### Проблема: "Поллинг уже запущен"

**Решение:**

```bash
pkill -9 -f main.py
rm -f *.lock
sleep 3
nohup python3 main.py > server.log 2>&1 &
```

### Проблема: "Множественные экземпляры"

**Решение:**

```bash
pkill -9 -f main.py
sleep 2
ps aux | grep main.py  # Проверить что все остановлены
nohup python3 main.py > server.log 2>&1 &
```

### Проблема: "Циклов проверки = 0"

**Решение:** Система не работает, нужен полный перезапуск (см. раздел 3)

### Проблема: "Сигналы не отправляются"

**Проверка:**

```bash
# Есть ли кандидаты?
grep -c "candidate" system_improved.log

# Есть ли trend_ok?
grep -c "trend_ok" system_improved.log

# Проверить Telegram
grep "Bot authorized\|Polling" server.log | tail -2
```

---

## 📱 ВАЖНО ДЛЯ СЕРВЕРА:

На сервере должен использоваться **PROD токен**, а не DEV!

Проверьте:

```bash
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
env = os.getenv('ATRA_ENV', 'dev')
print(f'Окружение: {env}')
if env == 'prod':
    print('✅ Используется PROD токен')
else:
    print('⚠️  Используется DEV токен! Установите: export ATRA_ENV=prod')
"
```
