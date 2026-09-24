# Stability & Performance Watchdog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Создать автономную систему, которая предотвращает перегрузку Mac Studio (Backpressure) и автоматически оптимизирует производительность БД.

**Architecture:**

1. **Backpressure Layer:** Ограничение очереди задач в БД и контроль ресурсов перед запуском.
2. **Observation Layer:** Активация `pg_stat_statements` и сбор метрик.
3. **Action Layer:** Автономное применение индексов и настроек через `CodebaseMutationEngine`.

**Tech Stack:** Python, PostgreSQL (pg_stat_statements), Docker API, asyncpg.

---

### Task 1: Backpressure - Ограничение очереди задач

**Files:**

- Modify: `knowledge_os/app/smart_worker_autonomous.py`
- Modify: `knowledge_os/app/enhanced_orchestrator.py`

**Step 1: Внедрить лимит MAX_PENDING_TASKS**
Добавить проверку количества задач со статусом `pending` перед генерацией новых. Лимит: 10 задач.

**Step 2: Проверить ограничение**
Создать 11 тестовых задач и убедиться, что 11-я не создаётся или блокируется.

**Step 3: Commit**

```bash
git add knowledge_os/app/smart_worker_autonomous.py knowledge_os/app/enhanced_orchestrator.py
git commit -m "feat: add backpressure - limit pending tasks to 10"
```

---

### Task 2: Инфраструктура - Активация pg_stat_statements

**Files:**

- Modify: `knowledge_os/docker-compose.yml`

**Step 1: Добавить shared_preload_libraries**
В секцию `db` (knowledge_postgres) добавить `-c shared_preload_libraries=pg_stat_statements`.

**Step 2: Перезапустить БД и проверить расширение**
`docker compose restart db`
`SELECT * FROM pg_stat_statements LIMIT 1;`

**Step 3: Commit**

```bash
git add knowledge_os/docker-compose.yml
git commit -m "infra: enable pg_stat_statements in postgres"
```

---

### Task 3: Watchdog - Сбор и анализ медленных запросов

**Files:**

- Create: `knowledge_os/app/performance_watchdog.py`

**Step 1: Реализовать сборщик (Collector)**
Класс, который раз в 10 минут забирает топ-5 медленных запросов из `pg_stat_statements`.

**Step 2: Реализовать интеграцию с Victoria (Analyzer)**
Отправка плана запроса (`EXPLAIN`) в `ai_core` для генерации гипотезы оптимизации.

**Step 3: Commit**

```bash
git add knowledge_os/app/performance_watchdog.py
git commit -m "feat: implement performance watchdog collector and analyzer"
```

---

### Task 4: Action - Автономное применение оптимизаций

**Files:**

- Modify: `knowledge_os/app/performance_watchdog.py`
- Modify: `knowledge_os/app/codebase_mutation_engine.py`

**Step 1: Реализовать безопасный исполнитель SQL**
Метод для выполнения `CREATE INDEX CONCURRENTLY` с проверкой `pg_advisory_lock`.

**Step 2: Добавить логику Rollback**
Замер скорости после оптимизации. Если стало хуже — `DROP INDEX`.

**Step 3: Commit**

```bash
git add knowledge_os/app/performance_watchdog.py knowledge_os/app/codebase_mutation_engine.py
git commit -m "feat: add autonomous SQL execution and rollback to watchdog"
```

---

### Task 5: Integration - Запуск Watchdog как сервиса

**Files:**

- Modify: `knowledge_os/docker-compose.yml`

**Step 1: Добавить сервис performance-watchdog**
Новый контейнер на базе образа `victoria-agent`, запускающий `performance_watchdog.py`.

**Step 2: Проверить логи и алерты в Telegram**
Убедиться, что события оптимизации приходят в чат.

**Step 3: Commit**

```bash
git add knowledge_os/docker-compose.yml
git commit -m "infra: deploy performance-watchdog service"
```
