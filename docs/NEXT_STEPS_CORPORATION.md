# Следующие шаги корпорации (по аудиту и рекомендациям куратора)

**Источники:** CORPORATION_FULL_AUDIT_2026-02-08, VERIFICATION_2026-02-08, VICTORIA_CURATOR_PLAN. **Обновлено:** 2026-02-09.

**Когда корпорация станет «как я» и что дальше по плану:** см. [ROADMAP_CORPORATION_LIKE_AI.md](ROADMAP_CORPORATION_LIKE_AI.md).

---

## 1. Уже сделано (рекомендации внедрены)

- **Единый источник текста «что ты умеешь»:** `configs/victoria_capabilities.txt` + `configs/victoria_common.get_capabilities_text()`. Используют `victoria_server` и `victoria_enhanced`; при отсутствии файла — fallback в коде. Переменная окружения `VICTORIA_CAPABILITIES_FILE` для кастомного пути.
- **Куратор и наставник:** расширен VICTORIA_CURATOR_PLAN (§5 — эталоны, передача в knowledge_nodes, чеклист); добавлен **CURATOR_CHECKLIST.md** для разбора отчётов; цель — «лучшая корпорация в своём деле».
- **RAG-кэш:** ленивое вытеснение устаревших записей (не более 50 за вызов) в Victoria — уже в коде.

---

## 2. RAG-кэш в Redis (при масштабировании)

**Сделано (2026-02-10):** в `victoria_server.py` добавлен переключатель **RAG_CACHE_BACKEND=memory|redis**. По умолчанию `memory`. При `redis` кэш контекста RAG хранится в Redis: ключ `rag_ctx:{md5(goal)}`, TTL из **RAG_CACHE_TTL_SEC**; используется **REDIS_URL** (тот же, что у knowledge_os/backend). При недоступности Redis запрос идёт в БД без кэша (логируется на DEBUG). Зависимость: `redis` (в knowledge_os и backend уже есть).

**Когда включать:** при втором инстансе Victoria или при желании общий кэш между сервисами. Пока один инстанс — оставить `RAG_CACHE_BACKEND=memory`.

---

## 3. Дальнейшие улучшения по чеклисту куратора

- **Эталоны в standards/:** накапливать в `docs/curator_reports/standards/` эталонные ответы по типам запросов; использовать при прогонах и при добавлении в knowledge_nodes.
- **Эталоны в RAG (сделано):** скрипт `scripts/curator_add_standard_to_knowledge.py` добавляет в knowledge_nodes все 5 эталонов (домен curator_standards); RAG находит по ILIKE.
- **verbose steps в API (сделано):** в POST /run можно передать `"verbose": true` в теле запроса; в ответе в `knowledge.verbose_steps` возвращаются пошаговые шаги агента (thought, tool, tool_input) для маршрута agent_run. Для async-режима то же в GET /run/status/{task_id}.
- **Скоринг «как я» (сделано):** скрипт `scripts/curator_compare_to_standard.py` — сравнение отчёта с эталоном: `--report path/to/curator_*.json --standard what_can_you_do` (или greeting, status_project, list_files, one_line_code). Выводит совпадение ключевых фраз эталона с ответом.

---

## 4. После успешного прогона куратора (5/5)

**Проверено (2026-02-08):** полный прогон 23-16-02 — 5/5 success (в т.ч. «список файлов» 92.7 с); backend 37 тестов — passed.

**При «продолжай» дальше:**
- Периодически запускать полный прогон: `./scripts/run_curator_scheduled.sh` (или `./scripts/run_curator.sh --file scripts/curator_tasks.txt --async --max-wait 600`); разбирать отчёт по CURATOR_RUNBOOK и CURATOR_CHECKLIST; при необходимости — `curator_compare_to_standard.py --report ... --standard ...` и запрос с `verbose: true` для пошаговых шагов.
- При сбоях «список файлов» — см. **curator_reports/CURATOR_LIST_FILES_FAILURES.md** → «При следующих сбоях».
- По желанию при масштабировании: RAG Redis (§2).

---

## 5. План оркестратора: подсказка или исполнение (решение зафиксировано)

**Текущее состояние (VICTORIA_TASK_CHAIN_FULL §6):** IntegrationBridge возвращает assignments и strategy, но Victoria **только подставляет их в контекст** (промпт). Реального «поставить задачу эксперту X в БД и дождаться результата» в рамках POST /run нет.

**Принятое решение:** по умолчанию **план выполняется** (исполнение по assignments): в docker-compose для victoria-agent задано **EXECUTE_ASSIGNMENTS_IN_RUN=true**. [execute_assignments.py](knowledge_os/app/execute_assignments.py) вызывает run_smart_agent_async по каждому эксперту из плана оркестратора, результаты подставляются в контекст Victoria (план «как я» п.12.2 п.1). Отключить: задать EXECUTE_ASSIGNMENTS_IN_RUN=false в .env. При вопросах «почему план не выполняется» — проверять доступность оркестратора и экспертов; см. VICTORIA_TASK_CHAIN_FULL §6–7.

---

## 6. Связь с библией

- При внедрении RAG Redis — обновить MASTER_REFERENCE (RAG+, кэш), VERIFICATION_CHECKLIST §5 (при изменении RAG/Victoria).
- Эталоны и чеклист куратора — часть методологии «сверяться с библией и обновлять её» (.cursorrules).
- После прогонов куратора — при необходимости обновлять FINDINGS и INDEX в docs/curator_reports/.
- **Как что делать (команда и агенты):** единый индекс — [HOW_TO_INDEX.md](HOW_TO_INDEX.md).