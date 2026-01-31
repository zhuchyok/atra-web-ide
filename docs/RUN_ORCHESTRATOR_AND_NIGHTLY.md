# Запуск оркестратора и Nightly Learner

## Что сделано

- **Redis:** Для контейнеров в atra-network используется `REDIS_URL=redis://knowledge_redis:6379` (не atra-redis). Скрипты и cron передают эту переменную.
- **Блокировка:** Один ключ Redis `lock:heavy_process` — одновременно может работать только один тяжёлый процесс (оркестратор или Nightly Learner). Освободить вручную: `docker exec knowledge_redis redis-cli DEL "lock:heavy_process"`.
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
- Поиск по нашим меткам: `[ENHANCED_ORCHESTRATOR]`, `[NIGHTLY_LEARNER]`, `[LOG_INTERACTION]`, `[DELEGATION]`.
