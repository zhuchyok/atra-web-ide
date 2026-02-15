# Как что делать — единый индекс для команды и агентов

**Назначение:** одна точка входа для ответа «как сделать X». Для **команды** (разработка, эксплуатация) и для **агентов** (Victoria, эксперты): при вопросе пользователя «как добавить эксперта», «как запустить куратор», «как применить миграции» — открыть этот документ и по таблице перейти к нужному runbook или команде.

**Обновлено:** 2026-02-11

---

## Для кого

- **Люди:** разработчики, SRE, кураторы — по индексу находить пошаговые инструкции.
- **Victoria / эксперты:** при запросе «как что сделать» использовать этот индекс (и связанные документы из §8 MASTER_REFERENCE), чтобы дать точную ссылку и команды.

---

## Индекс: тема → что делать → где смотреть

| Тема | Что нужно сделать | Где смотреть / команда |
|------|-------------------|-------------------------|
| **Эксперты** | Добавить нового эксперта в систему | [EXPERT_CONNECTION_ARCHITECTURE.md](EXPERT_CONNECTION_ARCHITECTURE.md) §4 (runbook): 1) запись в `configs/experts/employees.json`, 2) `python scripts/sync_employees.py`, 3) при необходимости — правило в `.cursor/rules/` и строка в `team.md`, 4) применить seed в БД (Docker). |
| **Куратор** | Запустить прогон куратора (быстрый / полный / по расписанию) | [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md): быстрый — `./scripts/run_curator.sh`; полный — `./scripts/run_curator.sh --file scripts/curator_tasks.txt --async --max-wait 600`; cron — `./scripts/run_curator_scheduled.sh`. **При запуске из IDE/CI с таймаутом:** задавать timeout ≥ 10 мин (--quick) или ≥ 30 мин (полный), иначе процесс убивается по внешнему лимиту. См. VERIFICATION §3, §5. |
| **Куратор** | Разобрать отчёт, сравнить с эталоном, добавить эталоны в RAG | [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) §2–3; чеклист — [curator_reports/CURATOR_CHECKLIST.md](curator_reports/CURATOR_CHECKLIST.md); сравнение — `python3 scripts/curator_compare_to_standard.py --report ... --standard what_can_you_do`; в RAG — `scripts/curator_add_standard_to_knowledge.py`. |
| **Куратор-наставник** | Понять, как куратор «учит» Victoria (роль Cursor) | [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) §0: не при каждой задаче, а через эталоны, прогоны и обновление RAG; Victoria учится из контекста. |
| **Куратор при деплое** | После деплоя один раз прогнать быстрый прогон и сравнение с эталонами | [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) §1.5: `./scripts/run_curator_post_deploy.sh` (или `./scripts/run_curator_and_compare.sh`). Таймаут среды ≥ 10 мин. Опционально — шаг в pipeline после поднятия сервисов. |
| **Миграции БД** | Применить миграции Knowledge OS | В Docker — при старте API/воркера; вручную: `cd knowledge_os && .venv/bin/python scripts/apply_migrations.py` (или через `DATABASE_URL`). Канон схемы — [knowledge_os/db/init.sql](../knowledge_os/db/init.sql). |
| **Тесты** | Запустить все тесты (быстро / с БД / интеграционные) | [TESTING_FULL_SYSTEM.md](TESTING_FULL_SYSTEM.md): быстрый — `pytest backend/app/tests/ -q` и `pytest knowledge_os/tests/ -q -m "not integration and not slow"`; один скрипт — `./scripts/run_all_system_tests.sh`; с БД — `RUN_WITH_DB=1`; с Victoria — `RUN_INTEGRATION=1`. |
| **Таймаут среды при запуске скриптов** | Избежать «прервалось по таймауту» при запуске куратора/E2E/долгих скриптов из IDE или CI | [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §3 (причина «Прогон куратора прерывается»), §5: задавать **timeout среды** не меньше требуемого (куратор --quick ≥ 10 мин, полный ≥ 30 мин). Новые долгие скрипты — указывать в docstring/runbook рекомендуемый timeout запуска. См. [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) §1, [CONTRIBUTING.md](../CONTRIBUTING.md) §2. |
| **E2E (чат, health)** | Запустить Playwright E2E | [TESTING_FULL_SYSTEM.md](TESTING_FULL_SYSTEM.md) §2 «E2E (Playwright)»: `cd frontend && npm run e2e` (после поднятия frontend/backend). BASE_URL=3000, BACKEND_URL=8080. [CONTRIBUTING.md](../CONTRIBUTING.md) §2. |
| **Секреты** | Не хранить пароли в репо, настроить проду | [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §5: не коммитить `.env` с паролями; в проде — секрет-менеджер (Vault и т.д.). Шаблон без секретов: корень репо **.env.example**. [WHATS_NOT_DONE.md](WHATS_NOT_DONE.md) §2. |
| **Восстановление** | «Задачи не создаются», оркестратор 137, Ollama недоступен | [LIVING_ORGANISM_PREVENTION.md](LIVING_ORGANISM_PREVENTION.md) — что проверять; [ORCHESTRATOR_137_AND_OLLAMA.md](ORCHESTRATOR_137_AND_OLLAMA.md) — OOM, Ollama. Команды: `docker compose -f knowledge_os/docker-compose.yml up -d`; `ollama serve`; `bash scripts/system_auto_recovery.sh`; при webhook — `python3 scripts/host_recovery_listener.py`. |
| **RAG / база знаний** | Понять, кто и как использует накапливаемую базу | [KNOWLEDGE_BASE_USAGE.md](KNOWLEDGE_BASE_USAGE.md) — Victoria, Veronica, оркестраторы, эксперты, Telegram; откуда появляются узлы. |
| **Runbook по типу задачи** | Постоянное применение знаний: по типу запроса подтягиваются эталоны и похожие решения | Эталоны — домен **curator_standards** (статус, что умеешь, привет, список файлов); выполненные задачи — домен **victoria_tasks**. Victoria при ответе подтягивает RAG по смыслу; приоритет **usage_count** (часто используемое выше). «Похожие успешные решения» — до 2 записей из victoria_tasks в промпт. Добавить новый тип — эталон в [curator_reports/standards/](curator_reports/standards/) и при необходимости в RAG ([curator_add_standard_to_knowledge.py](../scripts/curator_add_standard_to_knowledge.py)). |
| **Деплой / запуск** | Порядок запуска, что перезагрузить после изменений | [MASTER_REFERENCE.md](MASTER_REFERENCE.md) §9: сначала Knowledge OS `docker compose -f knowledge_os/docker-compose.yml up -d`, затем Web IDE `docker compose up -d`; таблица «Что перезагрузить». |
| **Границы кода** | Где править: корпорация vs торговля | [SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md](SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md): корпорация — `knowledge_os/app/` и `src/agents/bridge/`; торговля — остальное `src/`. При правках сверять границы. |
| **Подход и логика** | Понять, как мы мыслим и обрабатываем задачи (для команды и агентов) | [THINKING_AND_APPROACH.md](THINKING_AND_APPROACH.md) — принципы, последовательность шагов (понять → контекст → план → выполнить → проверить → зафиксировать), принятие решений, неясности. В промпт Victoria подставляется **configs/corporation_thinking.txt** (блок «КАК МЫ МЫСЛИМ»). |
| **Логика мысли Victoria** | План внедрения единой линии рассуждения: выбор стратегии, память между диалогами, рефлексия и итерация плана, неопределённость | [PLAN_REASONING_LOGIC_VICTORIA.md](PLAN_REASONING_LOGIC_VICTORIA.md) — фазы 0–5, команда экспертов, мировые практики (MAR, ReCAP, LoCoMo), критерии и метрики. |
| **Что не сделано** | Увидеть открытые пункты и приоритеты | [WHATS_NOT_DONE.md](WHATS_NOT_DONE.md) — цепочка, масштаб, тесты, RAG, документация; при закрытии — обновлять документ и MASTER_REFERENCE. |
| **Цепочка задачи** | Как задача идёт от пользователя до ответа, кто исполняет | [VICTORIA_TASK_CHAIN_FULL.md](VICTORIA_TASK_CHAIN_FULL.md) — схема, план = подсказка (не исполнение в БД в рамках запроса). |
| **Проблемы и решения** | Сводка проблем с привязкой к экспертам и runbook | [PROBLEMS_AND_EXPERT_SOLUTIONS.md](PROBLEMS_AND_EXPERT_SOLUTIONS.md) — таблица + ссылки на runbook. |
| **Проверка корпорации** | Пошагово проверить, правильно ли делают; если нет — причина, как нужно, переделать | [CORPORATION_CHECK.md](CORPORATION_CHECK.md) — эксперты, тесты, библия, запуск, границы кода; что переделывать до правильного. |
| **Mac Studio / загрузка Victoria** | Учесть характеристики и нагрузку Mac Studio (память Docker, лимиты, вылеты Victoria) | [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md) — RAM, Docker 10–14 GB, MAX_CONCURRENT_VICTORIA, async_mode, USE_ELK; при вылетах — [VICTORIA_RESTARTS_CAUSE.md](VICTORIA_RESTARTS_CAUSE.md). |
| **Docker вылетает / не запускается** | Часто нехватка памяти (OOM) | [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md) §2.1 — лимит Memory 10–14 GB (мин. 8 GB), проверка OOMKilled, снижение RAG/мониторинга; [VICTORIA_RESTARTS_CAUSE.md](VICTORIA_RESTARTS_CAUSE.md) §2. |
| **MLX постоянно вылетает / как правильно использовать MLX** | Только лёгкие модели, роль «жизнедеятельность» | [MLX_STRATEGY_LIGHT_AND_VITALITY.md](MLX_STRATEGY_LIGHT_AND_VITALITY.md) — стратегия, команда (Дмитрий, Елена, Игорь), MLX_ONLY_LIGHT; [MLX_PYTHON_CRASH_CAUSE.md](MLX_PYTHON_CRASH_CAUSE.md). |
| **Копия «тебя» на Mac Studio: статус и продолжаем** | Что уже есть, что делать дальше (куратор, эталоны, план) | [MAC_STUDIO_COPY_STATUS.md](MAC_STUDIO_COPY_STATUS.md) — база «как я», приоритеты следующих шагов, быстрые команды. |
| **Добавление новой модели Ollama/MLX** | Замер холодного старта и занесение в справочники, чтобы таймауты учитывали время загрузки и обработки | [MASTER_REFERENCE.md](MASTER_REFERENCE.md) §4 «При добавлении новой модели»; [MODEL_COLD_START_REFERENCE.md](MODEL_COLD_START_REFERENCE.md) «Runbook: при добавлении новой модели». Команды: `MEASURE_SOURCE=ollama python scripts/measure_cold_start_all_models.py` или `MEASURE_SOURCE=mlx ...`; скрипт обновляет configs/ollama_model_timings.json или configs/mlx_model_timings.json. |
| **Выгрузка неиспользуемых моделей / модели висят в памяти** | Как устроена выгрузка MLX и Ollama, висят ли модели бесконечно | [MODEL_UNLOADING_AND_MEMORY.md](MODEL_UNLOADING_AND_MEMORY.md) — MLX: LRU, MLX_MAX_CACHED_MODELS (по умолчанию 1), периодическая очистка раз в 10 мин; Ollama: автовыгрузка ~5 мин, keep_alive в запросах. |
| **Runbook по типу задачи (постоянное применение знаний)** | Где хранить и как подставлять инструкции по типу задачи; похожие успешные решения | Эталоны — [curator_reports/standards/](curator_reports/standards/) и RAG домен **curator_standards** (скрипт `curator_add_standard_to_knowledge.py`). Выполненные задачи — домен **victoria_tasks** (пишет `_learn_from_task` в Victoria); при ответе подтягиваются похожие по тексту цели (usage_count в приоритете). Добавить новый тип: эталон в standards/ + при необходимости узел в knowledge_nodes (домен curator_standards или свой). |
| **RAG-кэш в Redis (масштабирование)** | Включить общий кэш контекста RAG между инстансами Victoria | [NEXT_STEPS_CORPORATION.md](NEXT_STEPS_CORPORATION.md) §2: задать **RAG_CACHE_BACKEND=redis** и **REDIS_URL** (тот же, что у knowledge_os). Ключ rag_ctx:{md5(goal)}, TTL из RAG_CACHE_TTL_SEC. По умолчанию memory (один инстанс). |
| **Nightly и обучение → видимость в RAG** | Дозаписать embedding для узлов knowledge_nodes без него (nightly_learner и др.; без embedding узлы не попадают в векторный RAG) | План «умнее быстрее» §4.1. Скрипт: `cd knowledge_os && python scripts/backfill_knowledge_embeddings.py [--limit N]` (по умолчанию 100 узлов). Использует get_embedding из semantic_cache (Ollama). Рекомендуемый timeout запуска: ≥ 5 мин при большом количестве узлов. |

---

## Быстрые команды (шпаргалка)

```bash
# Эксперты: синхронизация после правки employees.json
python scripts/sync_employees.py

# Куратор: полный прогон
./scripts/run_curator.sh --file scripts/curator_tasks.txt --async --max-wait 600

# Тесты: всё быстро (без БД, без live)
./scripts/run_all_system_tests.sh

# Восстановление контейнеров и сервисов
bash scripts/system_auto_recovery.sh

# Запуск стека (сначала Knowledge OS, потом Web IDE)
docker compose -f knowledge_os/docker-compose.yml up -d
docker compose up -d
```

---

## Связь с библией

- **MASTER_REFERENCE.md** §8 — таблица документов (туда входит и этот индекс).
- При добавлении нового runbook или пошаговой инструкции — добавить строку в таблицу выше и при необходимости обновить MASTER_REFERENCE §8.
