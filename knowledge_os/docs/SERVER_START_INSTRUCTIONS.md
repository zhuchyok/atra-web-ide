# ИНСТРУКЦИЯ ПО ЗАПУСКУ СЕРВИСА

## 🚀 Запуск сервиса после исправления

### 1. Обновите код и запустите сервис:

```bash
cd ~/atra
git pull
python3 start_service_correctly.py
```

### 2. Если автоматический запуск не сработал, выполните вручную:

#### Остановите старые процессы:

```bash
ps aux | grep python
kill -9 <PID>
```

#### Запустите сервис:

```bash
# Вариант 1: Простой запуск
python3 signal_live.py &

# Вариант 2: Запуск с логами
bash -c 'python3 signal_live.py > signal_live.log 2>&1 &'

# Вариант 3: Запуск main.py
python3 main.py &
```

### 3. Проверьте, что сервис работает:

```bash
# Проверьте процессы
ps aux | grep python

# Проверьте логи
tail -f signal_live.log
# или
tail -f main.log

# Проверьте базу данных
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
try:
    cursor.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime(\"now\", \"-24 hours\")')
    print('✅ signals запрос работает')
    cursor.execute('SELECT COUNT(*) FROM filter_checks WHERE created_at > datetime(\"now\", \"-24 hours\")')
    print('✅ filter_checks запрос работает')
    print('🎉 Проблема решена!')
except Exception as e:
    print(f'❌ Ошибка: {e}')
finally:
    conn.close()
"
```

## 🔧 Если проблемы продолжаются:

### Проверьте права доступа:

```bash
ls -la signal_live.py
chmod +x signal_live.py
```

### Проверьте зависимости:

```bash
python3 -c "import sqlite3, requests, pandas"
```

### Проверьте место на диске:

```bash
df -h
```

## ✅ После успешного запуска:

- ✅ Сервис запущен и работает
- ✅ База данных исправлена
- ✅ Все запросы работают корректно
- ✅ Ошибки "no such column: created_at" и "disk I/O error" исправлены

---

_Инструкция создана: 2025-10-07_
