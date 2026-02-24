# ЗАПУСК БОТА НА СЕРВЕРЕ

## 🚨 ПРОБЛЕМА: БОТ НЕ ЗАПУЩЕН!

Из проверки видно, что бот не запущен:

- ❌ `ps aux | grep -E "(signal_live|main\.py)"` - не показывает процессов
- ✅ Есть лог файлы (signal_live.log, system_improved.log)
- ✅ База данных работает

## 🚀 АВТОМАТИЧЕСКИЙ ЗАПУСК

### 1. Обновите код и запустите бота:

```bash
cd ~/atra
git pull
python3 start_bot_now.py
```

## 🔧 РУЧНОЙ ЗАПУСК

### Если автоматический запуск не сработал:

```bash
# Вариант 1: signal_live.py
python3 signal_live.py &

# Вариант 2: main.py
python3 main.py &

# Вариант 3: с логами
nohup python3 signal_live.py > signal_live.log 2>&1 &
```

### Проверьте после запуска:

```bash
ps aux | grep -E "(signal_live|main\.py)"
```

## 📋 ПРОВЕРКА РАБОТЫ

### 1. Проверьте процессы:

```bash
ps aux | grep python
```

### 2. Проверьте логи:

```bash
tail -f signal_live.log
# или
tail -f main.log
```

### 3. Проверьте базу данных:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime(\"now\", \"-24 hours\")')
print(f'📊 Сигналов за 24ч: {cursor.fetchone()[0]}')
cursor.execute('SELECT COUNT(*) FROM active_signals WHERE status = \"active\"')
print(f'📊 Активных сигналов: {cursor.fetchone()[0]}')
conn.close()
"
```

## ✅ ОЖИДАЕМЫЙ РЕЗУЛЬТАТ

После запуска вы должны увидеть:

- ✅ Процесс Python в `ps aux | grep python`
- ✅ Логи без ошибок в `tail -f signal_live.log`
- ✅ Статистика базы данных показывает активность
- ✅ Сообщения о работе ИИ системы

## 🆘 ЕСЛИ НЕ РАБОТАЕТ

### Проверьте зависимости:

```bash
python3 -c "import sqlite3, requests, pandas, talib"
```

### Проверьте права доступа:

```bash
ls -la signal_live.py
chmod +x signal_live.py
```

### Проверьте место на диске:

```bash
df -h
```

---

_Инструкция создана: 2025-10-07_
