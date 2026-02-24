# ИСПРАВЛЕНИЕ ОШИБКИ "no such column: status"

## 🚨 Проблема

Ошибка: **"no such column: status"** - отсутствует столбец status в таблицах

## 🚀 Быстрое исправление

### 1. Обновите код и запустите исправление:

```bash
cd ~/atra
git pull
python3 fix_status_column.py
```

### 2. Если автоматическое исправление не сработало, выполните вручную:

#### Проверьте структуру таблиц:

```bash
sqlite3 trading.db
```

В SQLite выполните:

```sql
-- Проверьте, какие таблицы есть
.tables

-- Проверьте структуру таблицы signals
PRAGMA table_info(signals);

-- Проверьте структуру таблицы active_signals
PRAGMA table_info(active_signals);

-- Добавьте столбец status в таблицу signals (если нужно)
ALTER TABLE signals ADD COLUMN status TEXT DEFAULT 'active';

-- Добавьте столбец status в таблицу active_signals (если нужно)
ALTER TABLE active_signals ADD COLUMN status TEXT DEFAULT 'active';

-- Выйдите из SQLite
.quit
```

### 3. Перезапустите сервис:

```bash
# Остановите процесс
ps aux | grep python
kill -9 <PID>

# Запустите заново
python3 signal_live.py &
# или
python3 main.py &
```

### 4. Проверьте результат:

```bash
# Проверьте процессы
ps aux | grep python

# Проверьте логи
tail -f signal_live.log

# Проверьте базу данных
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
try:
    cursor.execute('SELECT COUNT(*) FROM signals WHERE status = \"active\"')
    print('✅ signals с status работает')
    cursor.execute('SELECT COUNT(*) FROM active_signals WHERE status = \"active\"')
    print('✅ active_signals с status работает')
    print('🎉 Проблема решена!')
except Exception as e:
    print(f'❌ Ошибка: {e}')
finally:
    conn.close()
"
```

## 🔧 Дополнительные действия

### Если проблема повторяется:

1. **Проверьте все таблицы:**

```bash
sqlite3 trading.db "SELECT name FROM sqlite_master WHERE type='table';"
```

2. **Добавьте столбец status во все таблицы:**

```bash
sqlite3 trading.db "
ALTER TABLE signals ADD COLUMN status TEXT DEFAULT 'active';
ALTER TABLE active_signals ADD COLUMN status TEXT DEFAULT 'active';
ALTER TABLE filter_checks ADD COLUMN status TEXT DEFAULT 'active';
"
```

3. **Проверьте права доступа:**

```bash
ls -la trading.db
chmod 664 trading.db
```

## ✅ После исправления:

- ✅ Ошибка "no such column: status" исправлена
- ✅ Все таблицы имеют столбец status
- ✅ Сервис перезапущен
- ✅ Все запросы работают корректно

---

_Инструкция создана: 2025-10-07_
