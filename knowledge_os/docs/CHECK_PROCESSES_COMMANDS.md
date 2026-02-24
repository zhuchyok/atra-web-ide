# КОМАНДЫ ДЛЯ ПРОВЕРКИ ПРОЦЕССОВ

## 🔍 Проверка процессов Python

### 1. Все процессы Python:

```bash
ps aux | grep python
```

### 2. Только процессы приложения:

```bash
ps aux | grep -E "(signal_live|main\.py)"
```

### 3. Конкретный PID:

```bash
ps -p 22226
```

### 4. Детальная информация:

```bash
ps -ef | grep python
```

## 🧪 Автоматическая проверка

### Запустите скрипт проверки:

```bash
cd ~/atra
git pull
python3 check_processes.py
```

## 📋 Проверка логов

### Проверьте лог файлы:

```bash
# Если есть signal_live.log
tail -f signal_live.log

# Если есть main.log
tail -f main.log

# Проверьте размер логов
ls -la *.log
```

## 🔧 Если процесс не найден

### Запустите приложение:

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
ps aux | grep python
```

## 📊 Проверка работы базы данных

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

## ✅ Ожидаемый результат

Если все работает правильно, вы должны увидеть:

- ✅ Процесс Python с signal_live.py или main.py
- ✅ Логи без ошибок
- ✅ База данных отвечает на запросы
- ✅ Статистика показывает активность

---

_Инструкция создана: 2025-10-07_
