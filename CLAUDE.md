# ATRA Web IDE

Multi-agent AI system with Victoria as team lead, 88 experts, PostgreSQL, Redis, Ollama.

## Architecture

- **Victoria** (port 8010) → `victoria-wisdom-24k:latest` (num_ctx=24576, ~7.9GB RSS)
- **Backend** (port 8080) → FastAPI
- **Ollama** (port 11434) → MLX API
- **PostgreSQL** (port 5432) → knowledge_os DB, 91,328 records, 88 experts
- **Redis** → streams for expert task routing

## Expert Workers

| Worker     | Expert          | Stream    |
| ---------- | --------------- | --------- |
| dynamic-1  | Инна (overflow) | overflow  |
| dynamic-2  | Юлия (overflow) | overflow  |
| anna-1     | Анна            | dedicated |
| victoria-1 | Виктория        | dedicated |
| heavy-1    | heavy tasks     | dedicated |

## Key Files

- `src/agents/bridge/victoria_server.py` — Victoria server, model routing, concurrency semaphore
- `src/agents/core/executor.py` — executor model selection
- `knowledge_os/app/expert_stream_routing.py` — task dispatch (overflow/dedicated/shared)
- `knowledge_os/app/expert_worker.py` — worker startup, consumer groups
- `knowledge_os/app/enhanced_orchestrator.py` — orchestrator dispatch
- `knowledge_os/app/medic/log_scanner.py` — rate limiting (5 tasks/hour)
- `knowledge_os/app/medic/watchdog.py` — health monitoring
- `knowledge_os/docker-compose.agents.yml` — container config

## Current State (Sept 2026)

- Victoria model: `victoria-wisdom-24k` (switched from v3.5, 6x faster response)
- Veronica model: `qwen3-coder:30b` (switched from qwen2.5-coder:14b)
- All containers healthy, 0 pending tasks
- Overflow routing fixed (dispatch_stream_for_expert checks is_overflow_expert)
- Overflow pool: 5 workers (dynamic-1-5)
- Docker VM: 24GB
- Grafana alerts → Telegram (AtlE bot `vikoria_atra_bot`, chat 556251171)
- Alert `deferred-to-human-high`: `knowledge_os_tasks_deferred_new_24h_total > 10` (pipeline A→reduce→math)
- Prometheus scrapes knowledge_rest:8002 (deferred metrics)
- Old monitoring stack (atra-grafana, atra-prometheus, atra-kibana, atra-elasticsearch) остановлен (restart=no, volumes сохранены)
- Исторический бэклог 65 deferred задач помечен `deferred_review_done=true` (13.09.2026)

## Super-Agent Roadmap (сент 2026) — ЗАВЕРШЕН

1. **Latency**: concrete goal fast-path (skip strategy+understand LLM) — 58s → 1-2s
2. **RAG NaN purge** (1,177 poisoned vectors) + CollectiveMemory.query_knowledge фоллбек на hybrid search по knowledge_nodes
3. **web_search tool** (SearxNG primary, DDG fallback) + явные tool-директивы обходят clarification
4. **db_query** (read-only SQL, SELECT/WITH/EXPLAIN + DDL guard) + git_status/git_diff/git_log
5. **Overflow-пул 2→5 воркеров** (compose YAML anchors, слоты 3-5)
6. **Discovery hijack fix**: classify_query на оригинальном запросе (до RAG-обогащения)
7. **Deterministic-gen больше не пишит** src/generated_file\*.py для web-задач

## Остаток (низкий приоритет)

- ~~Тулы (web_search/db_query/git) доступны в deep-пути; в quick-пути пока «подсказки команд»~~ ✅ DONE (00.14.09.2026: quick-route исполняет тулы до LLM через `_run_quick_tools_for_goal`)
- ~~MLX сервер запускается вручную~~ ✅ DONE (launchd `com.atra.mlx-api-server`, preload wisdom-24k + phi3.5)
- ~~Semantic cache freshness guard~~ ✅ DONE (env vars SEMANTIC_CACHE_ENFORCE_FRESHNESS=true, SEMANTIC_CACHE_FRESHNESS_SLA_SEC=900)
- ~~Autonomous code endpoint~~ ✅ DONE (`/api/autonomous-code`: goal → Veronica → code → file → py_compile → result)

## Super-Agent v2 (сент 2026) — ЗАВЕРШЕН

1. **Self-fix loop** (`/api/autonomous-code` v2): py_compile → runtime smoke → трейсбек Veronica → 3 иттерации автофикса. Проверено E2E (iters, passed)
2. **Опыт в knowledge_nodes**: `/api/commit-experience` (kind=experience, дедуп sha1 goal+outcome); autonomous-code и orchestrate-plan пишут опыт сами
3. **Планировщик** (`/api/orchestrate-plan`): цель → LLM-декомпозиция `[{title,goal}]` (raw_decode-сканер переживает битые JSON) → исполнение через autonomous-code → сводный отчёт. `DIALOGUE_MAX_TOKENS=1500` в victoria-agent
4. **Telegram alert test**: пряма доставка боту подтверждена (message_id 1943); contact point file-provisioned (bottoken REDACTED, chatid 556251171); policy default=telegram. Сквозной Grafana→Telegram route (unified alertmanager dispatch) — не подтверждён боем (time-box); fallback-канал — прямой bot. Alert rule `deferred-to-human-high` активна
5. **Чистка**: 51 мусорный файл из src/ удалён (test/generated артефакты прошлых сессий); мусорные тестовые демо-скрипты физически снесены
6. **Guardian**: `smollm2:360m` вместо phi3.5:3.8b (GIT_GUARDIAN_MODEL/DIALOGUE_*_MODEL в .env), fast pre-commit

Известные ограничения:
- Veronica пишет в `/app/src` (mounted to host src/) — ок
- **Coder выделенный**: Veronica + autonomous-code работают через отдельный Ollama-инстанс `127.0.0.1:11436` (OLLAMA_CODER_URL в victoria-agent, OLLAMA_EXECUTOR_BASE_URL в veronica-agent; models через symlink blobs ~/.ollama-veronica; qwen3-coder keep_alive=-1). Причина: конкуренция с wisdom-24k на 11434 порождала IndentError/фрагменты классов/циклы. Сплит-геноверация: plan 5/5 passed за 160с
- **indent normalizer** в autonomous-code: rank уровней → 4n, автоматически до py_compile
- Alertmanager dispatch path (10.2 катом): rule фёрится, local notifier получает; AM→Telegram dispatch в Калиальном runtime не стреляет (требует отдельную internal DS grafana для публикации — пробовалось, не победено). РАБОЧИЙ канал: `scripts/tg_deferred_alerts.py` (LaunchAgent `com.atra.tg-deferred-alerts`): Prometheus при каждом 5m опрашивает `knowledge_os_tasks_deferred_new_24h_total > 10` → telegram_alerter (дедуп 4h, state tmp/tg_deferred_alerts.state). Проверено: fetch ok, доставка бота honeok (msg 1943/1946)
- pre-commit hook задаёт host URLs через env (.env: OLLAMA_BASE_URL, MLX_BASE_URL)

## Замеры Super-Agent v2 (15.09.2026)

- **Guardian (pre-commit)**: smollm2:360m → 2-6с вместо прежних 30-90с, fail-open при ambiguous
- **Опыт-цикл**: задача №1 категории — 17с (LLM+RAG); задача №2 той же категории — **3с (5.7x быстрее)** — semantic cache + experience-нода. Опыт сам пишется в knowledge_nodes при каждом autonomous-code/planner прогоне
- **Вн v3 planner** (`2026-09-15`): Re-plan on failure проверен E2E (нарушенный шаг → LLM-ре-декомпозиция с err-контекстом → replaced, итог passed, replans_used=1)
- **Topological deps**: plans use `depends` + parallel on independentНе steps with Semaphore(2) — but LLM often ignores field; planner разбивает по уровням стаб.
- **sanity-check v3.3**: after each passed step — quick LLM "OK/NO" от Victoria поверх file (fail-open nếu model из-за недоступности), failed → status "sanity_failed" → replan Chain
- **Experience retrieval v3.4**: перед планом топ-3 релевантных опыts (tsvector по knowledge_nodes, kind=experience; фоллбек newest). Проверено E2E
- **Гит-агент v3** (15.09): тулы git_branch_create/add/commit/push/pr_list/test_run — write-ready, зарегистрированы в Veronica (ALLOWED_TOOLS). `git_pr_create` делает честную underbox (gh недоступен в контейнере — host-only). TDD-loop в autonomous-code (`test_path`): тест генерится до кода, гоняется после runtime → fail-цепочка фикс-иттераций. Проверено E2E (`stage test0 passed`). `/api/self-review` — 5-пунктовая Victoria-оценка для PR (ревью для `src/tdd_impl.py` вернула Amber с понятными замечаниями)
- **Multi-task dispatcher v4.1** (`/api/saga`): N целей → по очереди/параллельно через orchestrate-plan v3 (replan+sanity+experience) → сводный отчёт по каждой; failures изолированы. E2E: 3 цели → 3/3 цель passed (6 шагов, 128с, 0 ре-планов — plan痊愈)
- **gh CLI внутри Victoria/Veronica контейнеров установлен** (GH_TOKEN env через compose, apt gh). `git_pr_create` теперь честный work-aware: `gh pr list` E2E из контейнера ✅; Dockerfile обновлён (gh в apt); минимум 2 рестарта пересоздали

Известные ограничения:

## Замеры Super-Agent v2 (15.09.2026)

- **Guardian (pre-commit)**: smollm2:360m → 2-6с вместо прежних 30-90с, fail-open при ambiguous
- **Опыт-цикл**: задача №1 категории — 17с (LLM+RAG); задача №2 той же категории — **3с (5.7x быстрее)** — semantic cache + experience-нода. Опыт сам пишется в knowledge_nodes при каждом autonomous-code/planner прогоне
- **Phase telemetry (v3.5 hardware-aware)**: autonomous-code возвращает `llm_ms/compile_ms/runtime_ms/test_ms` — телеметрия per phase. Target: llm ≤ 10s cold/3s warm; compile ≤ 100ms; кодer `num_ctx=8192` в direct generate (KV-cache 45.5GB → 20.2GB, освобождено 25GB unified)
- **Цели по железу**: quick-route ≤ 5s, autonomous-code 10s cold/3s warm, план 5 шагов ≤ 60s warm/120s cold, сага ≤ 45с/цель. (Не п95 40-60s из чужого плана: qwen3-coder 30b + wisdom 24k занимают 42GB unified и работать параллельно 5 слотами не могут — ограничение Semaphore(2) верное)
- **Faza 4.2 redis-mode работает** (16.09): dynamic-воркеры personnel на 11436 (OLLAMA_EXECUTOR_BASE_URL), `orchestrate_plan` dispatch через redis_manager.push_to_stream("expert_tasks:overflow") + pre-insert task-row + poll `tasks.result`. E2E: 2 шага 45с, файлы на src/, dispatch_mode=redis. Шаг A+Шаг B. Re-plan/sanity не тронуто.
- **Sanity-check: туда файл-контент + nonce** (16.09): `_sanity_check` читает первые 1600 симв кода в промпт (уплощает ответ), nonce `[sn:x]` против кеш-мис-совпадений, retry-проход пересчитывает sanity_ok (было null после dispatch timeout). E2E: `기감 2 шага` → 2/2 sanity True
- **Mojibake fix**: `_fix_mojibake` восстановление utf8-read-as-latin1 (replan-ȶх) на пути `_parse_steps`; проверено: 0 фейков на E2E плана
- **Watchdog v4.2-QUALITY** (16.09): per-handoff таймаут — `early_async_analysis` → 180с (env `VICTORIA_ASYNC_WATCHDOG_SEC`, 0 отключает), остальные → 600с (`VICTORIA_ASYNC_HARD_TIMEOUT_SEC`). Приёмка-критерий: **0 вечных processing** (проверено: task → failed через 180с с SLA-логом)
- **Hung-алерт отделён от p95**: `hung_fired_at` отдельный дедуп-ключ в state (ложный p95-page больше не глушит hang)
- **Wisdom-guard** (`scripts/ollama_wisdom_guard.py` + LaunchAgent `com.atra.ollama-wisdom-guard`): каждые 10мин выгружает `victoria-wisdom*` из Ollama 11434 (keep_alive=0), чтобы MLX-мозг не дублировался в обah Витam; лог: logs/ollama_wisdom_guard.out.log
