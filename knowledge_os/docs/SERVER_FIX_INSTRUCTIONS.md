# ИНСТРУКЦИЯ ПО ИСПРАВЛЕНИЮ ОШИБКИ НА СЕРВЕРЕ

## 🚨 Проблема

Ошибка: **"no such column: created_at"**

## 🔧 Быстрое исправление

### Вариант 1: Автоматическое исправление

```bash
cd ~/atra
python3 quick_fix_server.py
```

### Вариант 2: Ручное исправление

1. **Подключитесь к базе данных:**

```bash
cd ~/atra
sqlite3 trading.db
```

2. **Создайте таблицу filter_checks (если не существует):**

```sql
CREATE TABLE IF NOT EXISTS filter_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    filter_type TEXT,
    passed INTEGER DEFAULT 0,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_filter_checks_created_at ON filter_checks(created_at);
```

3. **Добавьте столбец created_at в signals_log (если не существует):**

```sql
ALTER TABLE signals_log ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;
CREATE INDEX IF NOT EXISTS idx_signals_log_created_at ON signals_log(created_at);
```

4. **Выйдите из SQLite:**

```sql
.quit
```

### Вариант 3: Обновление кода

Если проблема в коде, обновите файлы:

1. **Обновите web/dashboard.py:**

```python
# Замените эту строку:
cursor.execute("SELECT COUNT(*) FROM signals WHERE created_at > datetime('now', '-24 hours')")

# На эту:
cursor.execute("SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime('now', '-24 hours')")
```

2. **Обновите enhanced_health_check.py:**

```python
# Замените эту строку:
cursor.execute("SELECT MAX(created_at) FROM signals WHERE created_at IS NOT NULL")

# На эту:
cursor.execute("SELECT MAX(datetime(ts)) FROM signals WHERE ts IS NOT NULL")
```

## 🧪 Проверка исправления

После исправления проверьте:

```bash
cd ~/atra
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

## 📋 Что было исправлено

1. **SQL запросы** - исправлены обращения к неправильным столбцам
2. **Таблица filter_checks** - добавлена в схему базы данных
3. **Индексы** - созданы для оптимизации производительности
4. **Столбец created_at** - добавлен в signals_log

## ✅ Результат

После применения исправлений ошибка **"no such column: created_at"** больше не должна возникать.

---

_Инструкция создана: 2025-10-07_
