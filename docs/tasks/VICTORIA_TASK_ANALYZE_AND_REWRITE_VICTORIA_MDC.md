# Задание для Виктории: анализ и переписывание victoria.mdc

**Файл правил:** `.cursor/rules/victoria.mdc`  
**Цель:** Проанализировать документ на устаревшие формулировки и переписать его в актуальном виде.

**Правило (все должны знать):** Куратор даёт задание Виктории **всегда через скрипт** `scripts/curator_send_tasks_to_victoria.py --file docs/tasks/VICTORIA_TASK_ANALYZE_AND_REWRITE_VICTORIA_MDC.txt --async --max-wait 600`. Результат появится в `docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json` и `.md`. См. VICTORIA_USAGE_GUIDE, CURATOR_RUNBOOK §0, .cursorrules.

---

## Постановка задачи (goal для POST /run или для файла .txt)

Скопируй блок ниже в файл `.txt` и запусти **скрипт куратора** (рекомендуется). Либо отправь через Task или POST /run (см. варианты ниже).

```
Проект: atra-web-ide. Путь к репо: /Users/bikos/Documents/atra-web-ide (или workspace root).

Задача: проанализировать файл .cursor/rules/victoria.mdc на устаревшие формулировки и переписать его.

Что сделать по шагам:

1. Изучи текущий victoria.mdc (все разделы).

2. Свериться с актуальными источниками:
   - docs/MASTER_REFERENCE.md (разделы Wisdom Era, порты, последние изменения);
   - docs/CHANGES_FROM_OTHER_CHATS.md (последние §§ — номера версий, даты, новые возможности);
   - docs/PORT_REGISTRY.md (порты Victoria, Veronica, MLX, Ollama и т.д.);
   - knowledge_os/docker-compose.yml (USE_VICTORIA_ENHANCED, ENABLE_EVENT_MONITORING, RECOVERY_WEBHOOK_URL, порты);
   - knowledge_os/app/available_models_scanner.py (OLLAMA_BEST_FIRST, MLX_BEST_FIRST, имена моделей);
   - knowledge_os/app/local_router.py (OLLAMA_MODELS_FALLBACK, MLX_MODELS_FALLBACK);
   - knowledge_os/app/ollama_keep_alive_policy.py (FALLBACK_BRAIN_MODELS, keep_alive);
   - src/agents/bridge/victoria_server.py (эндпоинты: /run, /orchestrate, /run/status, параметры TaskRequest).

3. Выявить устаревшее:
   - номер/название эры (Singularity 21.5 vs 24.0 или иное в MASTER_REFERENCE);
   - даты в заголовках («Инвентарь 2026-03-05», «План B.1 2026-03-06») — актуализировать или убрать;
   - имена моделей (victoria-wisdom-v3.5, phi3.5:3.8b и т.д.) — сверять с кодом;
   - порты (8010, 8011, 11434, 11435, 9099) — сверять с PORT_REGISTRY и кодом;
   - эндпоинты (/run vs /orchestrate для execution_plan) — по victoria_server.py;
   - статусы «в разработке» (План B.1, B.2) — по CHANGES и коду определить, что уже внедрено;
   - ссылки на документы (INVENTORY, CURATOR_RUNBOOK и т.д.) — проверить существование путей.

4. Результат оформить в виде отчёта:
   - краткий список «что устарело» с обоснованием;
   - полный обновлённый текст victoria.mdc (или пораздельный diff), готовый к подстановке в файл.

5. Не менять смысл разделов (Золотой стандарт, три уровня, Мозг и Руки, метод экспертов, когнитивный кодекс). Менять только фактические данные (версии, даты, порты, имена, статусы) и формулировки, которые противоречат коду или библии.

Контекст: пользователь восстановил Золотой стандарт (делегирование через Task/API); в MASTER_REFERENCE и .cursorrules это уже закреплено. В victoria.mdc §0 тоже есть это определение — оставить по смыслу, при необходимости слегка унифицировать формулировки с MASTER_REFERENCE.
```

---

## Как отправить задание

**Вариант 1 — скрипт куратора (рекомендуется, все должны так делать):**  
Куратор всегда даёт задание через скрипт — тогда отчёт сохраняется и «Виктория сделала» = появление файла в curator_reports.

```bash
python3 scripts/curator_send_tasks_to_victoria.py --file docs/tasks/VICTORIA_TASK_ANALYZE_AND_REWRITE_VICTORIA_MDC.txt --async --max-wait 600
```

Результат в `docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json` и `.md`. Таймаут среды ≥ 10 мин. См. VICTORIA_USAGE_GUIDE, CURATOR_RUNBOOK §0.

**Вариант 2 — делегирование через Task:**  
Вставь текст goal как goal для субагента (локальная Виктория). Субагент получит контекст Библии и выполнит анализ + переписывание.

**Вариант 3 — стриминг (видеть шаги в реальном времени):**  
`POST http://localhost:8010/stream` с телом `{"goal": "<текст из .txt>", "project_context": "atra-web-ide", "max_steps": 80}`. Ответ — SSE поток (шаги thought/step, затем итог). См. **docs/VICTORIA_USAGE_GUIDE.md** § «Куратор: как ставить задачи».

**Вариант 4 — curl (async + ручной опрос, только если скрипт недоступен):**

```bash
curl -X POST "http://localhost:8010/run?async_mode=true" \
  -H "Content-Type: application/json" \
  -d '{"goal": "<вставь сюда текст goal из блока выше>", "project_context": "atra-web-ide", "max_steps": 50}'
```

Затем опрашивай `GET http://localhost:8010/run/status/{task_id}` до `status=completed`; в теле ответа будет поле `output` с отчётом Виктории.

(Файл goal уже есть: `docs/tasks/VICTORIA_TASK_ANALYZE_AND_REWRITE_VICTORIA_MDC.txt`. Предпочтительно всегда использовать Вариант 1 — скрипт куратора.)

---

## Ожидаемый результат

- Отчёт: что устарело, с указанием источника истины (файл + строка или §).
- Готовый обновлённый текст `.cursor/rules/victoria.mdc` (или патч), который можно применить в репо.
- После применения — обновить docs/CHANGES_FROM_OTHER_CHATS.md записью вида: «Виктория: актуализация victoria.mdc (версии, даты, порты, статусы Плана B) по результатам анализа».
