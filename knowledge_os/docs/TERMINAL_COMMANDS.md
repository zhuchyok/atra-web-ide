# 📋 КОМАНДЫ ДЛЯ ТЕРМИНАЛА

## 🚀 Управление ботом:

### Перезапуск бота (чистый):

```bash
./restart_bot_clean.sh
```

### Проверка статуса:

```bash
# Сколько процессов запущено
ps aux | grep main.py | grep -v grep | wc -l

# Показать процессы
ps aux | grep main.py | grep -v grep

# PID бота
ps aux | grep main.py | grep -v grep | awk '{print $2}'
```

### Остановка бота:

```bash
# Мягкая остановка
pkill -f main.py

# Принудительная остановка
pkill -9 -f main.py
```

### Запуск бота:

```bash
nohup python3 main.py > main.log 2>&1 &
```

---

## 📝 Мониторинг логов:

### Основные логи в реальном времени:

```bash
tail -f system_improved.log
```

### Логи запуска:

```bash
tail -f main.log
```

### Последние 50 строк:

```bash
tail -50 system_improved.log
```

### Поиск по логам:

```bash
# Найти сигналы
grep "candidate" system_improved.log | tail -20

# Найти ошибки
grep "ERROR" system_improved.log | tail -20

# Найти предупреждения
grep "WARNING" system_improved.log | tail -20
```

---

## 🔍 Проверка сигналов:

### Проверить сигналы за сегодня:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM signals WHERE date(ts) >= date(\"now\")')
print(f'Сигналов за сегодня: {cursor.fetchone()[0]}')
cursor.execute('SELECT symbol, side, ts FROM signals ORDER BY ts DESC LIMIT 5')
print('\\nПоследние 5 сигналов:')
for row in cursor.fetchall():
    print(f'  {row[2]}: {row[0]} {row[1]}')
conn.close()
"
```

### Последние сигналы из логов:

```bash
tail -100 system_improved.log | grep "candidate"
```

---

## 📊 Мониторинг системы:

### Запустить мониторинг:

```bash
python3 terminal_monitor.py
```

### Простой мониторинг:

```bash
watch -n 5 'ps aux | grep main.py | grep -v grep'
```

### Статистика процесса:

```bash
# CPU и память
top -pid $(ps aux | grep main.py | grep -v grep | head -1 | awk '{print $2}')
```

---

## 🗄️ Работа с базой данных:

### Открыть базу:

```bash
sqlite3 trading.db
```

### Быстрые запросы:

```bash
# Количество сигналов
sqlite3 trading.db "SELECT COUNT(*) FROM signals"

# Последние 5 сигналов
sqlite3 trading.db "SELECT symbol, side, datetime(ts, 'localtime') FROM signals ORDER BY ts DESC LIMIT 5"

# Активные сигналы
sqlite3 trading.db "SELECT COUNT(*) FROM active_signals WHERE status='active'"
```

---

## 🔧 Отладка:

### Проверить, работает ли Telegram бот:

```bash
python3 check_telegram_bot.py
```

### Проверить структуру базы:

```bash
python3 check_database_structure.py
```

### Проверить активность бота:

```bash
python3 check_bot_activity.py
```

---

## 💾 Бэкапы:

### Создать бэкап базы:

```bash
cp trading.db "trading_backup_$(date +%Y%m%d_%H%M%S).db"
```

### Список бэкапов:

```bash
ls -lh backups/
```

---

## 🎯 Быстрые проверки:

### Всё в одном:

```bash
echo "=== СТАТУС СИСТЕМЫ ==="
echo "Процессы: $(ps aux | grep main.py | grep -v grep | wc -l)"
echo "Последний лог: $(tail -1 system_improved.log)"
echo "Сигналов сегодня: $(sqlite3 trading.db 'SELECT COUNT(*) FROM signals WHERE date(ts) >= date(\"now\")')"
```

---

## 📱 Для сервера:

Скопируйте эти команды на сервер:

```bash
# Перейти в директорию
cd ~/atra

# Перезапустить
./restart_bot_clean.sh

# Мониторинг
tail -f system_improved.log

# Статус
ps aux | grep main.py | grep -v grep
```
