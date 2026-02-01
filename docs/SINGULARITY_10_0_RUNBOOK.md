# Runbook: Singularity 10.0 — Ручной запуск цикла

**Дата:** 2026-01-27  
**Версия:** 1.0

---

## Ручной запуск Nightly Learner (включает apply_all_knowledge)

### Через Docker (recommended)

```bash
# Убедитесь, что knowledge_postgres, knowledge_redis доступны
docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
  -e REDIS_URL=redis://knowledge_redis:6379 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e MLX_API_URL=http://host.docker.internal:11435 \
  victoria-agent python3 /app/knowledge_os/app/nightly_learner.py
```

### Локально (из knowledge_os/app)

```bash
cd knowledge_os/app
export DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os
export OLLAMA_BASE_URL=http://localhost:11434
python3 nightly_learner.py
```

---

## Ручной запуск Knowledge Applicator

```bash
cd knowledge_os
export DATABASE_URL=postgresql://admin:secret@localhost:5432/knowledge_os
python3 scripts/apply_knowledge.py
```

---

## Применение миграции prompt_change_log

```bash
psql $DATABASE_URL -f knowledge_os/db/migrations/add_prompt_change_log.sql
```

---

## Проверка метрик Singularity 10.0

Откройте дашборд: http://localhost:8501  
Вкладка **Singularity 9.0** — внизу секция **Singularity 10.0 — Автономия и применение знаний**.

Метрики:
- **Improvements per cycle (7d)** — knowledge_nodes за 7 дней
- **Success rate (tasks)** — % completed за 30 дней
- **Prompt evolutions (7d)** — prompt_change_log за 7 дней
- **Knowledge transfer (7d)** — knowledge_bridge/applicator за 7 дней

---

## Troubleshooting

1. **apply_knowledge.py: ModuleNotFoundError observability.knowledge_applicator**  
   Запускайте из каталога `knowledge_os` (не из корня репо).

2. **prompt_change_log не существует**  
   Примените миграцию: `psql $DATABASE_URL -f knowledge_os/db/migrations/add_prompt_change_log.sql`

3. **Knowledge Bridge не пишет в knowledge_nodes**  
   Убедитесь, что DATABASE_URL указывает на PostgreSQL Knowledge OS.
