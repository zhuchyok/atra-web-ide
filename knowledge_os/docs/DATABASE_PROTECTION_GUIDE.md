# 🛡️ ЗАЩИТА БАЗЫ ДАННЫХ - ПОЛНОЕ РУКОВОДСТВО

## ❌ ПРОБЛЕМА: Частое повреждение БД

### Симптомы:

```
❌ file is not a database
❌ disk I/O error
❌ user_data_dict пуст
```

---

## 🔍 ПРИЧИНЫ ПРОБЛЕМЫ

### 1. **Множественные экземпляры Database**

```python
# main.py
Database()  # ← Экземпляр 1

# telegram_handlers.py
db = Database()  # ← Экземпляр 2

# telegram_commands.py
db = Database()  # ← Экземпляр 3

# signal_live.py
db = Database()  # ← Экземпляр 4+
```

**Проблема:** Каждый создает свое соединение → конфликты при записи

### 2. **Одновременная запись из разных компонентов:**

- 📊 Main loop (генерация сигналов)
- 💬 Telegram handlers (команды пользователей)
- 📈 Price monitor (обновление позиций)
- 🤖 AI learning (сохранение паттернов)
- 💱 Arbitrage checker (проверка арбитража)

### 3. **Внезапные остановки процессов:**

```bash
pkill -9 -f main.py  # ← Убивает процесс БЕЗ graceful shutdown
```

**Результат:**

- WAL файлы не синхронизируются
- Транзакции не завершаются
- БД остается в неконсистентном состоянии

### 4. **SQLite ограничения:**

- Одновременная запись из разных процессов → блокировки
- Timeout 30s → если блокировка дольше → ошибка
- WAL mode помогает, но не полностью решает проблему

---

## ✅ РЕАЛИЗОВАННЫЕ РЕШЕНИЯ

### 1. **Автоматическая проверка и восстановление БД** ✅

**Файл:** `db_health_monitor.py`

**Функции:**

- ✅ `check_db_integrity()` - проверка целостности
- ✅ `auto_fix_database()` - автовосстановление
- ✅ `restore_from_backup()` - восстановление из бэкапа
- ✅ `checkpoint_wal()` - синхронизация WAL
- ✅ `get_db_health_status()` - полный статус здоровья

**Интеграция в main.py:**

```python
async def initialize_database_on_startup():
    # 🛡️ ЗАЩИТА: Проверяем здоровье БД перед запуском
    from db_health_monitor import auto_fix_database, get_db_health_status

    health = get_db_health_status()

    if not health["integrity_ok"]:
        logger.warning("⚠️ БД повреждена! Запуск автоматического восстановления...")
        if auto_fix_database():
            logger.info("✅ БД успешно восстановлена!")
```

### 2. **WAL Mode включен** ✅

**Файл:** `db.py`

```python
self.conn.execute("PRAGMA journal_mode=WAL;")
self.conn.execute("PRAGMA synchronous=NORMAL;")
self.conn.execute("PRAGMA busy_timeout=30000;")  # 30s
```

**Преимущества:**

- ✅ Concurrent читатели НЕ блокируют писателей
- ✅ Лучшая производительность
- ✅ Меньше блокировок

### 3. **Автоматические бэкапы** ✅

**Где:** В `db.py` уже есть функция `backup_file()`

**Что делает:**

- Создает бэкап перед критическими операциями
- Сохраняет в `backups/` с timestamp

---

## 🚀 ДОПОЛНИТЕЛЬНЫЕ РЕКОМЕНДАЦИИ

### 1. **Graceful Shutdown вместо `pkill -9`**

**❌ ПЛОХО:**

```bash
pkill -9 -f main.py  # Убивает процесс мгновенно
```

**✅ ХОРОШО:**

```bash
pkill -15 -f main.py  # SIGTERM - дает время на закрытие
# ИЛИ
kill -15 <PID>
```

**Еще лучше - используй скрипт:**

```bash
#!/bin/bash
# safe_stop.sh

echo "🛑 Останавливаем бота безопасно..."

# Получаем PID
PID=$(ps aux | grep 'python3 main.py' | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "✅ Бот не запущен"
    exit 0
fi

# Отправляем SIGTERM
kill -15 $PID

# Ждем 10 секунд
echo "⏳ Ждем завершения (10 сек)..."
sleep 10

# Проверяем, завершился ли процесс
if ps -p $PID > /dev/null; then
    echo "⚠️ Процесс не завершился, используем SIGKILL..."
    kill -9 $PID
else
    echo "✅ Бот остановлен корректно"
fi

# Делаем WAL checkpoint
echo "🔄 Синхронизация WAL..."
python3 -c "from db_health_monitor import checkpoint_wal; checkpoint_wal()"

echo "✅ Готово!"
```

### 2. **Регулярный мониторинг БД**

Добавь в cron:

```bash
# Каждый час проверяем здоровье БД
0 * * * * cd /root/atra && python3 -c "from db_health_monitor import get_db_health_status; print(get_db_health_status())"

# Каждые 6 часов делаем WAL checkpoint
0 */6 * * * cd /root/atra && python3 -c "from db_health_monitor import checkpoint_wal; checkpoint_wal()"
```

### 3. **Singleton pattern для Database**

**Создай файл:** `db_singleton.py`

```python
"""
Singleton Database instance для предотвращения множественных соединений
"""
import threading
from db import Database

_db_instance = None
_db_lock = threading.Lock()


def get_database() -> Database:
    """
    Получить единственный экземпляр Database

    Thread-safe singleton pattern
    """
    global _db_instance

    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = Database()

    return _db_instance


# Экспортируем для удобства
db = get_database()
```

**Затем в других файлах:**

```python
# ❌ ПЛОХО:
from db import Database
db = Database()  # Создает новое соединение!

# ✅ ХОРОШО:
from db_singleton import db  # Использует существующее соединение
```

### 4. **Ежедневный VACUUM**

Добавь в cron:

```bash
# Каждую ночь в 3:00
0 3 * * * cd /root/atra && python3 -c "from db_health_monitor import optimize_database; optimize_database()"
```

### 5. **Monitoring скрипт**

**Создай:** `monitor_db_health.sh`

```bash
#!/bin/bash
# monitor_db_health.sh - мониторинг здоровья БД

cd /root/atra

echo "🔍 Проверка здоровья БД..."

python3 << EOF
from db_health_monitor import get_db_health_status, auto_fix_database
import json

health = get_db_health_status()

print("📊 Статус БД:")
print(json.dumps(health, indent=2, ensure_ascii=False))

if not health["integrity_ok"]:
    print("\n⚠️ БД ПОВРЕЖДЕНА! Запуск автовосстановления...")
    success = auto_fix_database()
    if success:
        print("✅ БД восстановлена!")
    else:
        print("❌ Не удалось восстановить БД!")
        exit(1)
else:
    print("\n✅ БД в порядке!")

# Checkpoint WAL для безопасности
from db_health_monitor import checkpoint_wal
checkpoint_wal()
EOF
```

Запускай раз в час:

```bash
chmod +x monitor_db_health.sh

# В cron:
0 * * * * /root/atra/monitor_db_health.sh >> /root/atra/logs/db_monitor.log 2>&1
```

---

## 📊 ТЕСТИРОВАНИЕ

### Тест 1: Проверка текущего состояния

```bash
cd /root/atra
python3 -c "from db_health_monitor import get_db_health_status; import json; print(json.dumps(get_db_health_status(), indent=2))"
```

### Тест 2: Ручное восстановление

```bash
cd /root/atra
python3 -c "from db_health_monitor import auto_fix_database; auto_fix_database()"
```

### Тест 3: WAL Checkpoint

```bash
cd /root/atra
python3 -c "from db_health_monitor import checkpoint_wal; checkpoint_wal()"
```

---

## 🎯 ЧЕКЛИСТ ЗАЩИТЫ

- [x] ✅ Автоматическая проверка БД при запуске
- [x] ✅ Автоматическое восстановление из бэкапов
- [x] ✅ WAL mode включен
- [ ] ⏳ Singleton pattern для Database
- [ ] ⏳ Graceful shutdown скрипт
- [ ] ⏳ Cron мониторинг
- [ ] ⏳ Ежедневный VACUUM

---

## 📝 ИТОГ

### ✅ Что уже работает:

1. Автоматическая проверка БД при каждом запуске
2. Автовосстановление из бэкапов
3. WAL mode для лучшей concurrent работы
4. Регулярные бэкапы

### 🔄 Что нужно сделать:

1. Использовать graceful shutdown вместо `pkill -9`
2. Внедрить singleton pattern для Database
3. Настроить cron мониторинг
4. Добавить ежедневный VACUUM

### 🚀 Результат:

- ✅ БД автоматически восстанавливается при повреждении
- ✅ Меньше конфликтов при записи (WAL)
- ✅ Всегда есть свежие бэкапы
- ✅ Мониторинг здоровья БД

**Проблема с повреждением БД должна значительно уменьшиться!** 🎉
