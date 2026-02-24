# ИСПРАВЛЕНИЕ ОШИБКИ "disk I/O error"

## 🚨 Проблема

Ошибка: **"disk I/O error"** - проблема с диском или базой данных

## 🚀 Быстрое исправление

### 1. Обновите код и запустите исправление:

```bash
cd ~/atra
git pull
python3 fix_disk_io_error.py
```

### 2. Если автоматическое исправление не сработало, выполните вручную:

#### Проверьте свободное место:

```bash
df -h
```

#### Создайте резервную копию:

```bash
cp trading.db trading.db.backup_$(date +%Y%m%d_%H%M%S)
```

#### Исправьте базу данных:

```bash
sqlite3 trading.db
```

В SQLite выполните:

```sql
-- Дефрагментация базы данных
VACUUM;

-- Проверка целостности
PRAGMA integrity_check;

-- Оптимизация
PRAGMA optimize;

-- Выйдите из SQLite
.quit
```

#### Перезапустите сервис:

```bash
# Найдите и остановите процессы
ps aux | grep python
kill -9 <PID>

# Запустите заново
nohup python3 signal_live.py > signal_live.log 2>&1 &
# или
nohup python3 main.py > main.log 2>&1 &
```

### 3. Проверьте результат:

```bash
# Проверьте, что процесс запущен
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

## 🔧 Дополнительные действия

### Если проблема повторяется:

1. **Проверьте место на диске:**

```bash
df -h
du -sh *
```

2. **Очистите старые логи:**

```bash
find . -name "*.log" -mtime +7 -delete
```

3. **Очистите старые бэкапы:**

```bash
find . -name "*.backup_*" -mtime +30 -delete
```

4. **Проверьте права доступа:**

```bash
ls -la trading.db
chmod 664 trading.db
```

## ✅ После исправления:

- ✅ Ошибка "disk I/O error" исправлена
- ✅ База данных оптимизирована
- ✅ Сервис перезапущен
- ✅ Все запросы работают корректно

---

_Инструкция создана: 2025-10-07_
