# Оркестрация V2: Canary Deployment (A/B)

## Что это

Постепенное внедрение **EnhancedOrchestratorV2**: часть трафика (по умолчанию 10%) идёт в V2, остальное — в существующую систему. Метрики пишутся в БД и в Prometheus для сравнения.

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `ORCHESTRATION_V2_ENABLED` | `false` | Включить A/B: при `true` часть запросов идёт в V2. |
| `ORCHESTRATION_V2_PERCENTAGE` | `10` | Процент трафика в V2 (0–100). |

В `.env` и в `knowledge_os/docker-compose.yml` для Victoria уже заданы:
- `ORCHESTRATION_V2_ENABLED=true`
- `ORCHESTRATION_V2_PERCENTAGE=10`

## Миграция БД

Колонка `tasks.orchestrator_version` создаётся **автоматически при старте Knowledge OS API** (в `rest_api.py` — `startup`). Ручной запуск не нужен.

Если API не поднимаете, миграцию можно применить вручную:
```bash
# Вариант 1: из контейнера Victoria (есть knowledge_os и asyncpg)
docker exec victoria-agent python3 -c "
import asyncio, asyncpg, os
sql = open('/app/knowledge_os/db/migrations/add_orchestrator_version.sql').read()
asyncio.run(asyncpg.connect(os.environ.get('DATABASE_URL')).execute(sql))
print('OK')
"

# Вариант 2: psql
psql \"\$DATABASE_URL\" -f knowledge_os/db/migrations/add_orchestrator_version.sql
```

## Метрики

- **Knowledge OS API**: `GET /metrics` и `GET /api/v2/orchestrate/metrics` — Prometheus-формат (оркестрация + A/B за последние 24 ч).
- **Prometheus** скрапит `knowledge_os_api:8000/metrics` (конфиг: `infrastructure/monitoring/prometheus.yml`). Контейнер API должен быть в сети `atra-network` вместе с Prometheus.
- **Grafana**: дашборд **Orchestration A/B Test** (uid: `orchestration-ab`) — сравнение V2 и existing (success rate, duration, распределение задач).

## Скрипты

- **Сбор A/B метрик из БД**:  
  `python3 scripts/collect_ab_metrics.py --hours 24` (или `--hours 4`), вывод: `--output json` или text.
- **Проверка и рекомендации по оптимизации**:  
  `python3 scripts/auto_optimize_orchestration.py --hours 6` (рекомендации без применения), с `--apply` — применить предложенные изменения (например, процент V2).

## Где что лежит

- Конфиг оркестрации: `knowledge_os/app/config.py` (ORCHESTRATION_V2_*).
- Мост A/B: `knowledge_os/app/task_orchestration/integration_bridge.py`.
- Запись задач в БД (orchestrator_version): `src/agents/bridge/victoria_server.py` (_record_orchestration_task_start/complete).
- Экспорт A/B в Prometheus: `knowledge_os/app/rest_api.py` (_ab_metrics_prometheus, GET /metrics).
- Дашборд A/B: `infrastructure/monitoring/grafana/provisioning/dashboards/orchestration_ab.json`.
