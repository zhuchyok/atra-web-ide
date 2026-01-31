# КОМАНДЫ ДЛЯ ПЕРЕЗАГРУЗКИ СЕРВЕРА

## 🚀 Выполните эти команды на сервере:

```bash
# 1. Обновите код
cd ~/atra
git pull

# 2. Запустите полное исправление и перезагрузку
python3 fix_and_restart.py
```

## 🔄 Если автоматическая перезагрузка не сработала:

### Вариант 1: PM2
```bash
pm2 restart all
pm2 list
```

### Вариант 2: Systemd
```bash
sudo systemctl restart atra
sudo systemctl status atra
```

### Вариант 3: Ручная перезагрузка
```bash
# Найдите процесс
ps aux | grep -E '(signal_live|main\.py)'

# Остановите процесс (замените PID на реальный)
kill -9 <PID>

# Запустите заново
nohup python3 signal_live.py > signal_live.log 2>&1 &
# или
nohup python3 main.py > main.log 2>&1 &
```

## 🧪 Проверка после перезагрузки:

```bash
# Проверьте логи
tail -f signal_live.log
# или
tail -f main.log

# Проверьте, что процесс запущен
ps aux | grep python

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

## ✅ После выполнения:

Ошибка **"no such column: created_at"** больше не должна возникать!
Сервис будет перезагружен с исправленной базой данных.
