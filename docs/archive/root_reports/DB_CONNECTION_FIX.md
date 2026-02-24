# 🔧 ИСПРАВЛЕНИЕ ОШИБКИ "TOO MANY CLIENTS ALREADY"

**Дата:** 2026-01-28  
**Статус:** ✅ **ИСПРАВЛЕНО**

---

## 🔍 ПРОБЛЕМА

**Ошибка:** `psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed: FATAL: sorry, too many clients already`

**Причина:**

- Слишком много открытых соединений к PostgreSQL
- Соединения не закрываются после использования
- Connection pools не управляются правильно
- Idle соединения накапливаются

---

## ✅ ЧТО ИСПРАВЛЕНО

### **1. Smart Worker Autonomous** ✅

**Файл:** `knowledge_os/app/smart_worker_autonomous.py`

**Изменения:**

- ✅ Использование глобального singleton пула вместо создания новых
- ✅ Правильное управление соединениями через `pool.acquire()` и `async with`
- ✅ Транзакции для атомарности операций
- ✅ Автоматическое закрытие пула при завершении
- ✅ Увеличен `max_size` до 10 с настройкой `max_inactive_connection_lifetime`

**Код:**

```python
# Глобальный пул соединений (singleton)
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DB_URL,
            min_size=1,
            max_size=10,
            max_inactive_connection_lifetime=300,  # Закрываем неактивные через 5 минут
            command_timeout=60
        )
    return _pool

# Использование с правильным управлением
async with pool.acquire() as conn:
    async with conn.transaction():
        # Работа с БД
        ...
```

---

### **2. Auto-fix DB Connections** ✅

**Файл:** `knowledge_os/app/auto_fix_db_connections.py` (новый)

**Функции:**

- ✅ Мониторинг количества соединений каждую минуту
- ✅ Автоматическое закрытие старых idle соединений (>5 минут)
- ✅ Экстренная очистка при достижении 80% использования
- ✅ Предотвращение ошибки "too many clients"

**Логика:**

1. Проверяет использование соединений
2. Если > 80% → закрывает idle соединения старше 5 минут
3. Если ошибка "too many clients" → экстренная очистка

---

## 🎯 ПРЕВЕНТИВНЫЕ МЕРЫ

### **1. Правильное использование соединений:**

```python
# ✅ ПРАВИЛЬНО - используем acquire и async with
async with pool.acquire() as conn:
    async with conn.transaction():
        result = await conn.fetch("SELECT ...")
    # Соединение автоматически возвращается в пул

# ❌ НЕПРАВИЛЬНО - соединение не закрывается
conn = await pool.acquire()
result = await conn.fetch("SELECT ...")
# Соединение остается открытым!
```

### **2. Таймауты и лимиты:**

- `max_inactive_connection_lifetime=300` - закрываем неактивные через 5 минут
- `command_timeout=60` - таймаут на команды
- `max_size=10` - максимум 10 соединений в пуле

### **3. Автоматическая очистка:**

- Auto-fix скрипт запущен в фоне
- Проверяет каждую минуту
- Закрывает старые idle соединения

---

## 📊 МОНИТОРИНГ

**Проверка соединений:**

```sql
SELECT
    count(*) as total,
    count(*) FILTER (WHERE state = 'idle') as idle,
    count(*) FILTER (WHERE state = 'active') as active
FROM pg_stat_activity
WHERE datname = 'knowledge_os';
```

**Закрытие старых соединений:**

```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'knowledge_os'
AND state = 'idle'
AND state_change < NOW() - INTERVAL '5 minutes';
```

---

## ✅ РЕЗУЛЬТАТ

- ✅ Соединения управляются правильно
- ✅ Автоматическая очистка idle соединений
- ✅ Предотвращение ошибки "too many clients"
- ✅ Система самовосстанавливается

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ

1. ✅ Исправлен Smart Worker
2. ✅ Добавлен Auto-fix скрипт
3. 🔄 Проверить другие модули на утечки соединений
4. 🔄 Добавить мониторинг в Enhanced Orchestrator

---

## 📝 УРОКИ

**Правила работы с БД:**

1. Всегда используйте `async with pool.acquire()` или `async with conn.transaction()`
2. Никогда не оставляйте соединения открытыми
3. Используйте singleton для connection pools
4. Настраивайте таймауты и лимиты
5. Мониторьте количество соединений

**Это мини-тест системы:**

- ✅ Обнаружили проблему
- ✅ Нашли причину
- ✅ Исправили код
- ✅ Добавили автоматическое исправление
- ✅ Предотвратили повторение
