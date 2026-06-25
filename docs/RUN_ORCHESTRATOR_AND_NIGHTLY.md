# Запуск оркестратора и Nightly Learner

## Что сделано

- **Redis:** Для контейнеров в atra-network используется `REDIS_URL=redis://knowledge_redis:6379` (не atra-redis). Скрипты и cron передают эту переменную.
- **Блокировка:** Один ключ Redis `lock:heavy_process` — lease lock с owner token + auto-renew + safe release. Используется для критических фаз оркестратора.
- **Ожидание lock:** `HEAVY_PROCESS_LOCK_WAIT_SEC` (default 30s). Если ожидание истекло, цикл не зависает бесконечно.
- **Важно:** lock может освобождаться перед тяжелыми фазами (`ORCHESTRATOR_RELEASE_LOCK_BEFORE_HEAVY_PHASES=true`), чтобы длинные R&D операции не блокировали весь контур.
- **Освободить вручную (аварийно):** `docker exec knowledge_redis redis-cli DEL "lock:heavy_process"`.
- **Скрипт оркестратора:** `./scripts/start_enhanced_orchestrator.sh once` — по умолчанию контейнер `victoria-agent`, Redis `knowledge_redis`.
- **Cron (ensure_autonomous_systems.sh):** В crontab для оркестратора и Nightly Learner добавлены `REDIS_URL=redis://knowledge_redis:6379` и для Nightly Learner — `OLLAMA_BASE_URL`, `MAC_LLM_URL` (host.docker.internal).

## Запуск вручную

```bash
# Освободить блокировку (если нужно)
docker exec knowledge_redis redis-cli DEL "lock:heavy_process"

# Оркестратор — один цикл
./scripts/start_enhanced_orchestrator.sh once

# Nightly Learner — один цикл (долго: эксперты + LLM)
docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
  -e REDIS_URL=redis://knowledge_redis:6379 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e MAC_LLM_URL=http://host.docker.internal:11435 \
  victoria-agent python3 -u /app/knowledge_os/app/nightly_learner.py
```

## Ошибка "too many clients already"

PostgreSQL отклоняет новые подключения из‑за лимита `max_connections`. Варианты:

- Увеличить `max_connections` у PostgreSQL (например в конфиге или переменной окружения контейнера knowledge_postgres).
- Временно остановить часть сервисов, держащих соединения (worker, dashboard, api и т.д.), затем снова запустить оркестратор/Nightly Learner.

## Логи

- Оркестратор: вывод в консоль и при запуске через скрипт — в `/tmp/enhanced_orchestrator.log`.
- Nightly Learner: при запуске через cron — `/tmp/nightly_learner.log`; при ручном запуске — консоль.
- Поиск по нашим меткам: `[ENHANCED_ORCHESTRATOR]`, `[NIGHTLY_LEARNER]`, `[LOG_INTERACTION]`, `[DELEGATION]`, `phase=1.95`, `released global lock before heavy phases`.

## Быстрая проверка runtime-контракта

```bash
# 1) Live workers heartbeat
docker exec knowledge_os_redis redis-cli HGETALL runtime:expert_heartbeats

# 2) Состояние глобального lock
docker exec knowledge_os_redis redis-cli GET lock:heavy_process
docker exec knowledge_os_redis redis-cli TTL lock:heavy_process

# 3) KPI срез
docker exec knowledge_postgres psql -U admin -d knowledge_os -Atc \
"SELECT 'completed_10m', count(*) FROM tasks WHERE status='completed' AND updated_at > NOW()-INTERVAL '10 minutes'
 UNION ALL
 SELECT 'in_progress_now', count(*) FROM tasks WHERE status='in_progress'
 UNION ALL
 SELECT 'pending_now', count(*) FROM tasks WHERE status='pending';"

# 4) SLA/fallback discipline (нет premature fallback)
docker exec knowledge_postgres psql -U admin -d knowledge_os -Atc \
"SELECT count(*) FROM tasks
 WHERE status='pending'
   AND COALESCE((metadata->>'stale_force_fallback')::boolean,false)=true;"
```
