# Задача для Victoria Agent: метрики STRICT_LOCAL в Prometheus

**Кому:** локальный агент Виктория (POST /run или MCP victoria_run / victoria_execute_plan)  
**Проект:** atra-web-ide  
**Источник:** план `.cursor/plans/strict_local_implementation_4869aab0.plan.md`, шаг 4 (Метрики) и шаг 10.

---

## Цель

Добавить экспорт трёх метрик режима STRICT_LOCAL в формате Prometheus, чтобы в Grafana можно было строить дашборды и настроить алерт: «STRICT_LOCAL включён, но локальные модели недоступны».

---

## Формулировка цели (goal) для POST /run

Скопируй блок ниже в `goal`:

```
Проект: atra-web-ide. Контекст: docs/MASTER_REFERENCE.md (раздел STRICT_LOCAL), knowledge_os/app/env_flags.py, knowledge_os/app/ai_core.py.

Задача: экспортировать метрики STRICT_LOCAL в Prometheus (для Grafana и алертов).

Что сделать:

1) Единое место для счётчиков (чтобы не хранить их только в атрибутах run_smart_agent_async):
   - В knowledge_os/app/env_flags.py добавить модульные переменные (или маленький класс-холдер):
     strict_local_qa_skip_count: int = 0
     strict_local_safety_skip_count: int = 0
   - И функции: increment_strict_local_qa_skip(), increment_strict_local_safety_skip(), get_strict_local_metrics() -> dict с полями enabled (bool), qa_skip_count (int), safety_skip_count (int).
   - В knowledge_os/app/ai_core.py во всех местах, где сейчас делается run_smart_agent_async._strict_local_qa_skip_count += 1 и _strict_local_safety_skip_count += 1, заменить на вызов env_flags.increment_strict_local_qa_skip() и increment_strict_local_safety_skip() соответственно (импорт env_flags или из app.env_flags в зависимости от контекста запуска).

2) Экспорт в GET /metrics Victoria:
   - В src/agents/bridge/victoria_server.py в обработчике GET /metrics (около строки 5813) добавить вывод трёх метрик в формате Prometheus exposition:
     - strict_local_enabled (gauge, 0 или 1) — значение 1 если is_strict_local() иначе 0. HELP: "STRICT_LOCAL mode is enabled (1) or disabled (0)"
     - strict_local_qa_skip_count (counter) — количество срабатываний QA reroute_to_cloud, не выполненных из-за STRICT_LOCAL. HELP: "QA reroute skipped due to STRICT_LOCAL"
     - strict_local_safety_skip_count (counter) — количество срабатываний safety reroute, не выполненных из-за STRICT_LOCAL. HELP: "Safety reroute skipped due to STRICT_LOCAL"
   - Значение strict_local_enabled брать из os.getenv("STRICT_LOCAL","").lower() in ("1","true","yes") при каждом запросе /metrics (или импорт is_strict_local из knowledge_os.app.env_flags если путь доступен; иначе дублировать проверку env в victoria_server).
   - Значения счётчиков брать из env_flags.get_strict_local_metrics() если модуль доступен; иначе выводить 0 для счётчиков (чтобы /metrics не падал при запуске без knowledge_os).

3) Документация:
   - В docs/MASTER_REFERENCE.md в разделе STRICT_LOCAL (метрики) добавить одну строку: «Метрики strict_local_* экспортируются в GET http://localhost:8010/metrics (Victoria Server).»
   - В docs/CHANGES_FROM_OTHER_CHATS.md добавить краткий параграф: реализован экспорт метрик STRICT_LOCAL в Prometheus (strict_local_enabled, strict_local_qa_skip_count, strict_local_safety_skip_count) в GET /metrics Victoria; счётчики перенесены в env_flags.

Не делать: менять логику блокировки облака в ai_core, safety_checker, quality_assurance. Не настраивать алерт в Grafana в коде (алерт настраивается вручную в UI Grafana: если strict_local_enabled == 1 и (mlx_health == down или ollama_health == down) → критический алерт).
```

---

## Как отправить задачу

### Вариант 1: curl (sync)

```bash
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Проект atra-web-ide. Задача: экспортировать метрики STRICT_LOCAL в Prometheus. (1) В env_flags.py добавить счётчики strict_local_qa_skip_count, strict_local_safety_skip_count и функции increment_*, get_strict_local_metrics(). (2) В ai_core.py заменить инкременты атрибутов run_smart_agent_async на вызовы env_flags.increment_*. (3) В victoria_server.py GET /metrics добавить вывод strict_local_enabled (gauge), strict_local_qa_skip_count (counter), strict_local_safety_skip_count (counter) в формате Prometheus. (4) Обновить MASTER_REFERENCE и CHANGES_FROM_OTHER_CHATS. Полное описание: docs/tasks/VICTORIA_TASK_STRICT_LOCAL_PROMETHEUS_METRICS.md",
    "project_context": "atra-web-ide",
    "max_steps": 30
  }'
```

### Вариант 2: с execution_plan (руки в IDE)

```bash
curl -X POST http://localhost:8010/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Реализовать экспорт метрик STRICT_LOCAL в Prometheus по заданию docs/tasks/VICTORIA_TASK_STRICT_LOCAL_PROMETHEUS_METRICS.md: env_flags — счётчики и get_strict_local_metrics; ai_core — вызовы increment_*; victoria_server GET /metrics — три метрики; обновить MASTER_REFERENCE и CHANGES.",
    "project_context": "atra-web-ide",
    "return_execution_plan": true
  }'
```

### Вариант 3: MCP (из Cursor)

В чате вызови инструмент `victoria_run` или `victoria_run_with_context` с goal из блока «Формулировка цели» выше (или кратко: «Выполни задание из docs/tasks/VICTORIA_TASK_STRICT_LOCAL_PROMETHEUS_METRICS.md»).

---

## Критерии приёмки

- В `knowledge_os/app/env_flags.py` есть счётчики и функции `increment_strict_local_qa_skip`, `increment_strict_local_safety_skip`, `get_strict_local_metrics()`.
- В `knowledge_os/app/ai_core.py` инкременты STRICT_LOCAL идут через env_flags, а не через атрибуты функции.
- `GET http://localhost:8010/metrics` возвращает строки вида:
  - `strict_local_enabled 0` или `1`
  - `strict_local_qa_skip_count 0` или больше
  - `strict_local_safety_skip_count 0` или больше
- MASTER_REFERENCE и CHANGES обновлены.

---

## Связанные файлы

- `knowledge_os/app/env_flags.py` — добавить счётчики и get_strict_local_metrics
- `knowledge_os/app/ai_core.py` — заменить атрибуты на вызовы env_flags (поиск по \_strict_local_qa_skip_count, \_strict_local_safety_skip_count)
- `src/agents/bridge/victoria_server.py` — обработчик GET /metrics (около 5813)
- `docs/MASTER_REFERENCE.md` — раздел STRICT_LOCAL
- `docs/CHANGES_FROM_OTHER_CHATS.md` — новый параграф
