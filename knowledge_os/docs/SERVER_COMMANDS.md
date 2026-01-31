# КОМАНДЫ ДЛЯ ИСПРАВЛЕНИЯ НА СЕРВЕРЕ

## 🚨 Выполните эти команды на сервере:

```bash
# 1. Обновите код
cd ~/atra
git pull

# 2. Запустите исправление базы данных
python3 fix_server_now.py

# 3. Если скрипт не работает, выполните вручную:
sqlite3 trading.db
```

## 📝 SQL команды для ручного исправления:

```sql
-- Создайте таблицу filter_checks
CREATE TABLE IF NOT EXISTS filter_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    filter_type TEXT,
    passed INTEGER DEFAULT 0,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Создайте индекс
CREATE INDEX IF NOT EXISTS idx_filter_checks_created_at ON filter_checks(created_at);

-- Добавьте столбец created_at в signals_log (если нужно)
ALTER TABLE signals_log ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- Создайте индекс для signals_log
CREATE INDEX IF NOT EXISTS idx_signals_log_created_at ON signals_log(created_at);

-- Выйдите из SQLite
.quit
```

## 🧪 Проверка исправления:

```bash
# Проверьте, что запросы работают
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

## ✅ После исправления:

Ошибка **"no such column: created_at"** больше не должна возникать!
