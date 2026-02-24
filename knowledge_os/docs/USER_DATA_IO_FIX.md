# ИСПРАВЛЕНИЕ ОШИБКИ "disk I/O error" ПРИ ЗАГРУЗКЕ ПОЛЬЗОВАТЕЛЬСКИХ ДАННЫХ

## 🚨 ПРОБЛЕМА

Ошибка: **"disk I/O error"** при загрузке пользовательских данных из БД

## 🚀 АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ

### 1. Обновите код и запустите исправление:

```bash
cd ~/atra
git pull
python3 fix_user_data_io_error.py
```

## 🔧 РУЧНОЕ ИСПРАВЛЕНИЕ

### Если автоматическое исправление не сработало:

#### 1. Проверьте свободное место:

```bash
df -h
```

#### 2. Создайте резервную копию:

```bash
cp trading.db trading.db.backup_$(date +%Y%m%d_%H%M%S)
```

#### 3. Исправьте базу данных:

```bash
sqlite3 trading.db
```

В SQLite выполните:

```sql
-- Проверка целостности
PRAGMA integrity_check;

-- Дефрагментация
VACUUM;

-- Оптимизация
PRAGMA optimize;

-- Проверка таблицы users_data
SELECT COUNT(*) FROM users_data;

-- Выйдите из SQLite
.quit
```

#### 4. Перезапустите бота:

```bash
# Остановите процесс
ps aux | grep python
kill -9 <PID>

# Запустите заново
python3 signal_live.py &
```

## 🧪 ПРОВЕРКА ИСПРАВЛЕНИЯ

### Проверьте загрузку пользовательских данных:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('trading.db')
cursor = conn.cursor()
try:
    cursor.execute('SELECT COUNT(*) FROM users_data')
    count = cursor.fetchone()[0]
    print(f'📊 Пользователей в БД: {count}')

    cursor.execute('SELECT user_id FROM users_data LIMIT 5')
    users = cursor.fetchall()
    print(f'📋 Первые пользователи: {[u[0] for u in users]}')

    print('✅ Загрузка пользовательских данных работает')
except Exception as e:
    print(f'❌ Ошибка: {e}')
finally:
    conn.close()
"
```

### Проверьте работу бота:

```bash
# Проверьте процессы
ps aux | grep python

# Проверьте логи
tail -f signal_live.log
```

## 🔧 ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ

### Если проблема повторяется:

1. **Очистите старые логи:**

```bash
find . -name "*.log" -mtime +7 -delete
```

2. **Очистите старые бэкапы:**

```bash
find . -name "*.backup_*" -mtime +30 -delete
```

3. **Проверьте права доступа:**

```bash
ls -la trading.db
chmod 664 trading.db
```

4. **Проверьте место на диске:**

```bash
du -sh *
```

## ✅ ПОСЛЕ ИСПРАВЛЕНИЯ

- ✅ Ошибка "disk I/O error" исправлена
- ✅ Пользовательские данные загружаются корректно
- ✅ База данных оптимизирована
- ✅ Бот перезапущен и работает стабильно

---

_Инструкция создана: 2025-10-07_
