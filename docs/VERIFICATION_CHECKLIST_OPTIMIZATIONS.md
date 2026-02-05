# Чеклист верификации оптимизаций (Speed without losing quality)

Документ для проверки результата после внедрения оптимизаций. **Рекомендации специалистов:** Backend (Игорь), QA (Анна), SRE (Елена), Performance (Ольга). Причины сбоев и меры, чтобы в будущем всё работало как нужно. Часть **методологии работы** (см. .cursorrules «Методология работы», MASTER_REFERENCE § «Как пользоваться»): советоваться с чеклистом, проверять результат, устранять причины сбоев, обновлять библию.

### Как применять рекомендации специалистов

| Когда | Что делать | Где смотреть |
|-------|------------|--------------|
| **Перед правками** в коде/конфиге | Определить затронутые компоненты (чат, воркер, Ollama/MLX, Victoria, Совет Директоров, дашборд, БД, API). Открыть **раздел 5 «При следующих изменениях»** — выполнить пункты по этим компонентам (например: новый код в воркере → run_in_executor; изменения в чате → контракт goal/project_context; изменения в потоке Совета → сохранять fallback и API_KEY). | §5 этого документа |
| **При появлении сбоя** (симптом: зависание, 503, эхо, пустой ответ, «не то решение») | Открыть **раздел 3 «Причины сбоев и как не допускать»** — найти проблему по таблице (Проблема / Причина / Решение). Исправить по решению и при необходимости дополнить таблицу новой строкой, чтобы в будущем не повторялось. | §3 этого документа |
| **После внедрения фичи или рефакторинга** | Пройти **раздел 1 «Что проверять»** по затронутым пунктам (например воркер/Ollama/MLX — п.14–19; чат — п.21; Совет Директоров — п.36). Запустить тесты (см. §2). При новой причине сбоя или новом правиле — добавить строку в §3 или пункт в §5. | §1, §2, при необходимости §3 и §5 |
| **Перед релизом** | Прогон тестов (json_fast, rest_api, victoria_chat_and_request); проверка health backend/Victoria/Veronica. Кратко зафиксировать в MASTER_REFERENCE или CHANGES, что чеклист учтён (какие пункты проверены). | §2, docs/MASTER_REFERENCE.md |

**«Учтены рекомендации»** значит: (1) перед правками прочитаны пункты §5 по затронутому компоненту; (2) при сбое использована таблица §3 и при необходимости она дополнена; (3) после правок проверены пункты §1 по области и при необходимости обновлены §3/§5.

---

## 0. План vs выполнение (Speed without losing quality)

| Пункт плана | Статус | Где |
|-------------|--------|-----|
| Пул БД (один на процесс) | Выполнено | db_pool.py; rest_api, collective_memory, context_analyzer |
| Параллельные fetch в ai_core (_get_knowledge_context) | Выполнено | ai_core.py: asyncio.gather для nodes и adaptive_learning_logs |
| Батч эмбеддингов в context_analyzer | Выполнено | context_analyzer: asyncio.gather + семафор для частей контекста |
| Документ: порядок перевода модулей на Rust | Выполнено | OPTIMIZATION_AND_RUST_CANDIDATES.md, раздел 6 |
| Общий httpx.AsyncClient (переиспользование) | Выполнено | http_client.py; semantic_cache.get_embedding; shutdown в rest_api |
| orjson в горячих путях | Выполнено | json_fast.py; semantic_cache, main.py (кэш поиска) |
| Кэш перед RAG | Выполнено | ai_core: сначала get_cached_response, при hit — без LLM/RAG |
| Стриминг ответов LLM | Уже реализован | backend: POST /api/chat/stream, SSE, StreamingProcessor, Victoria run_stream |
| Граничные случаи, resilience, lifespan, timezone | Выполнено | json_fast loads(None/""), main проверка кэша, rest_api/mlx lifespan, security/elk timezone.utc → timezone.utc |
| Тесты и чеклист | Выполнено | test_json_fast_http_client.py (8 тестов), test_rest_api (6), разделы 1–5 ниже |
| Адаптивный параллелизм воркера (N по CPU/MLX/Ollama) | Выполнено | adaptive_concurrency.py, smart_worker_autonomous: effective_N, семафор, лимиты тяжёлых, чередование блоков; см. ADAPTIVE_WORKER_CONCURRENCY_PLAN.md |

**Статус плана: завершён** (дата завершения: 2026-02-01).  
**Релиз выполнен** (2026-02-01): прогон тестов выполнен (14 passed), чеклист раздела 1 пройден. Запись: [RELEASE_SPEED_OPTIMIZATION_2026-02-01.md](RELEASE_SPEED_OPTIMIZATION_2026-02-01.md).
**Living Brain/Organism** (2026-02-03): чеклист пункты 27–35; тесты 23 passed (rest_api, json_fast, victoria_chat_and_request).

---

## 1. Что проверять (чеклист)

| № | Проверка | Как | Кто |
|---|----------|-----|-----|
| 1 | Пул БД: один на процесс | В rest_api, collective_memory, context_analyzer используется `db_pool.get_pool()`, не свой asyncpg.create_pool | Backend |
| 2 | HTTP-клиент: переиспользование | semantic_cache.get_embedding не создаёт новый AsyncClient на каждый вызов; при недоступности http_client — fallback на разовый клиент | Backend |
| 3 | Shutdown: закрытие клиента | rest_api при shutdown вызывает close_http_client() | SRE |
| 4 | JSON в горячих путях | semantic_cache (ответ Ollama) и main (кэш поиска) используют json_fast при наличии orjson | Backend |
| 5 | Кэш перед RAG | В ai_core: сначала get_cached_response, при hit — без LLM и без RAG | Backend |
| 6 | Граничные случаи кэша | main: при cached_data проверяем структуру (result_text, node_ids); при невалидном JSON — идём в поиск, не падаем | QA |
| 7 | Эмбеддинги: пустой ответ | semantic_cache: при пустом response.content возвращаем None, не падаем | QA |
| 8 | json_fast: None/пустая строка | loads(None), loads("") возвращают None; невалидный JSON — None | QA |
| 9 | REST API: lifespan | Используется lifespan (не deprecated on_event); shutdown вызывает close_http_client | Backend / SRE |
| 10 | Security: timezone-aware datetime | JWT exp/iat через datetime.now(timezone.utc), не utcnow() (deprecated) | Backend |
| 11 | Защищённый endpoint без токена | Ответ 401 Unauthorized (не 403); тест ожидает 401 | QA |
| 12 | MLX API Server: lifespan | mlx_api_server: lifespan вместо on_event; shutdown очищает кэш | Backend |
| 13 | ELK Handler: timezone-aware | elk_handler: datetime.now(timezone.utc) вместо utcnow() для @timestamp и index_name | Backend |
| 14 | Воркер: файловый enricher не блокирует loop | smart_worker_autonomous: enrich_task_with_file_context / enrich_task_with_multiple_files вызываются через run_in_executor | Backend / Performance |
| 15 | Воркер: пул БД для задач + heartbeats | get_pool(): max_size = max(15, SMART_WORKER_MAX_CONCURRENT + 8) | Backend |
| 16 | Воркер: сброс зависших и непрерывный пул | STUCK_MINUTES=15; обработка через семафор (не ждать весь батч) | SRE |
| 17 | Ollama/MLX: URL из env в Docker | LocalAIRouter.__init__ использует OLLAMA_API_URL/MLX_API_URL; сканер по умолчанию — env + host.docker.internal в Docker | Backend |
| 18 | Защита от эхо ответа | local_router: _is_echo_response(); при ответе = промпт — пробуем следующий узел, не возвращаем эхо | Backend |
| 19 | Воркер: батчи по модели | SMART_WORKER_BATCH_BY_MODEL=true; сканер моделей → preferred_model по категории → группировка по (source, model) → меньше load/unload на MLX/Ollama | Backend / Performance |
| 20 | Логика Victoria/Veronica/оркестратор/эксперты | PREFER_EXPERTS_FIRST соблюдается в двух слоях: (1) task_detector — «сделай/напиши код» → enhanced; (2) victoria_enhanced._should_delegate_task — в Veronica только простые одношаговые (_is_simple_veronica_request). Тесты: test_victoria_chat_and_request.TestPreferExpertsFirstDelegation | Backend / QA |
| 21 | Чат с Victoria: контракт и устойчивость | Backend: VictoriaClient.run() и run_stream() отправляют в Victoria body.goal и project_context (контракт POST /run — TaskRequest). При недоступности Victoria — health не ok → fallback MLX/Ollama; при ошибке run() — fallback; при любом исключении в sse_generator — try/except отдаёт сообщение и type: end. Слот снимается через with_victoria_slot в finally. При перегрузке — 503 + Retry-After | Backend / SRE |
| 22 | Адаптивный параллелизм воркера | При SMART_WORKER_ADAPTIVE_CONCURRENCY=true: effective_N по CPU/RAM и MLX/Ollama; при росте нагрузки N снижается, при разгрузке — в пределах floor/ceiling; логи раз в цикл (effective_concurrent, host_ram_percent, mlx_active, ollama_active). При ошибке расчёта — fallback на MAX_CONCURRENT | SRE / Backend |
| 23 | Пул БД воркера при адаптивном N | get_pool() в smart_worker_autonomous: max_size = max(15, SMART_WORKER_MAX_CONCURRENT + 8), чтобы хватало на задачи + heartbeats при любом effective_N | Backend |
| 24 | Тяжёлые/лёгкие модели и чередование блоков | Лимиты ADAPTIVE_MAX_HEAVY_MLX / ADAPTIVE_MAX_HEAVY_OLLAMA в первых слотах; SMART_WORKER_INTERLEAVE_BLOCKS=true — round-robin по блокам (MLX и Ollama одновременно) | Performance |
| 25 | Дашборд: актуальность счётчиков после «Обновить» | Вкладка «Автономные Задачи»: кнопка «Обновить» задаёт tasks_refresh_ts и сбрасывает кэш; запросы task_overview/recent_done с _cache_bust. Блок «Проверка БД» — маскированный DATABASE_URL и сырые счётчики по статусам (без кэша). Дашборд и воркер — один DATABASE_URL (knowledge_postgres в Docker) | SRE / Backend |
| 26 | cache_normalizer_rs в semantic_cache | semantic_cache._get_cached_embedding: try cache_normalizer.normalize_and_hash, fallback hashlib.md5. План Living Brain §5.2 п.9. | Backend |
| 27 | Tacit Knowledge в ai_core | is_coding_task определён ДО блока Tacit Knowledge; keywords расширены (напиши, создай, api, endpoint и др.). При отсутствии профиля — style_modifier пустой, не падаем | Backend / QA |
| 28 | Декомпозиция сложных задач (Phase 1.5) | Enhanced Orchestrator: priority=high/urgent или metadata.complex → Victoria decompose → подзадачи с parent_task_id. При отсутствии колонки parent_task_id — phase 1.5 skip (run add_task_orchestration_schema) | Backend |
| 29 | correlation_id по цепочке чат → Victoria | Backend chat: генерирует correlation_id, передаёт в VictoriaClient; VictoriaClient добавляет X-Correlation-ID; Victoria сервер читает заголовок и прокидывает в логах. SSE step содержит correlation_id | Backend / SRE |
| 30 | Dashboard auto-apply (safe) | AUTO_APPLY_DASHBOARD=true → dashboard_daily_improver._apply_max_entries_patch для st.cache_data без max_entries; только механическая замена; критичные — задачи | Backend / QA |
| 31 | Predictive Monitor | predictive_monitor.run_predictive_check: stuck in_progress (≥5 без обновления 15 мин), old pending (≥30 старше 1ч) → задачи SRE; внутри Self-Check | SRE |
| 32 | SSE progress events | Backend chat: type=progress { step, total, status } (analysis, executing, complete, error) | Backend |
| 33 | Батчинг мелких задач | Enhanced Orchestrator Phase 1.6: BATCH_SMALL_TASKS_ENABLED → metadata.batch_group по domain | Backend |
| 34 | Smart Worker batch LLM | SMART_WORKER_BATCH_GROUP_LLM=true → process_batch_tasks, формат [RESULT_N]...[/RESULT_N], fallback individual | Backend / Performance |
| 35 | Phase 16 doc sync task | nightly_learner: git log --merges 24h → при merge → задача «Синхронизировать документацию» (assignee_hint: Technical Writer) | Backend |
| 36 | Совет Директоров и чат | При стратегическом вопросе: is_strategic_question → POST /api/board/consult (X-API-Key); при ошибке/503 чат продолжает с Victoria без блока решения (fallback). Запись в board_decisions с session_id, user_id, source=chat. Дашборд 8501 — вкладка «Решения Совета». | Backend / SRE |
| 37 | Дедупликация задач от обучения (Curiosity) | Enhanced Orchestrator Phase 5 и Streaming _run_curiosity_engine перед созданием исследовательской задачи вызывают task_dedup.same_task_for_expert_in_last_n_days (title, description, assignee, 30 дней); при дубликате — skip с логом «Skip duplicate: same research task for … in last 30 days». Одна и та же задача (title+description) для одного эксперта не чаще раза в месяц. | Backend |

---

## 2. Как запускать проверки

### Юнит-тесты (QA, регрессия)

```bash
cd knowledge_os
.venv/bin/python -m pytest tests/test_json_fast_http_client.py -v
# или из корня репо: python3 -m pytest knowledge_os/tests/test_json_fast_http_client.py -v
```

Ожидание: все тесты зелёные (edge cases: пустая строка, None, невалидный JSON, idempotent close).

### REST API (здоровье и shutdown)

```bash
# Старт API
cd knowledge_os && uvicorn app.rest_api:app --host 0.0.0.0 --port 8012 &

# Проверка
curl -s http://localhost:8012/health | jq .

# Остановка (должен вызваться shutdown → close_http_client)
kill %1
```

В логах при остановке должно быть сообщение о закрытии HTTP-клиента (если уровень DEBUG).

### Зависимости (12-Factor)

```bash
cd knowledge_os
grep -E "orjson|httpx|asyncpg" requirements.txt
```

orjson и httpx должны быть только в requirements.txt, не устанавливаться в рантайме (без subprocess pip install в коде).

---

## 3. Причины сбоев и как не допускать

| Проблема | Причина | Решение (чтобы в будущем работало) |
|----------|---------|-------------------------------------|
| Падение при пустом кэше Redis | json.loads("") или loads(None) без проверки | loads возвращает None для None/""/b""; в main проверяем «if data and isinstance(data, dict) and "result_text" in data» |
| Падение при невалидном JSON в кэше | Старый формат или повреждённые данные | loads ловит JSONDecodeError/ValueError и возвращает None; main в except идёт в поиск |
| Падение при пустом ответе Ollama | response.content пустой | В _do_embed_request: «if not raw: return None» до парсинга |
| Утечка соединений HTTP | Новый AsyncClient на каждый get_embedding | Общий клиент в http_client.py; при ошибке get_http_client() — fallback на разовый клиент в контексте |
| Двойное закрытие клиента | Повторный вызов close_http_client | close проверяет _client is not None и после закрытия обнуляет; тест test_http_client_close_idempotent |
| Разные пулы БД в одном процессе | Каждый модуль создаёт свой create_pool | Единый db_pool.get_pool(); при миграции на Rust замена только в db_pool.py |
| Deprecation: on_event | FastAPI рекомендует lifespan | rest_api: @asynccontextmanager lifespan; startup + shutdown в одном контексте |
| Deprecation: datetime.utcnow() | В Python 3.12+ удаляется | security: datetime.now(timezone.utc) для JWT exp/iat |
| Тест ожидает 403 без токена | RFC: нет токена = 401 Unauthorized | test_rest_api: assert 401 |
| Задачи воркера «зависают» в in_progress | Синхронное чтение файлов (file_context_enricher) блокирует event loop → heartbeats не бегут | Вызов enricher через run_in_executor; см. WORKER_THROUGHPUT_AND_STUCK_TASKS.md |
| «20 задач в работе» при лимите 10 | Два экземпляра воркера (например knowledge_worker и knowledge_os_worker) или два контейнера | Один воркер на окружение; в docker-compose только knowledge_os_worker с SMART_WORKER_MAX_CONCURRENT=10; остановить старые контейнеры (docker ps -a). См. MLX_TASK_PROCESSING_CHECK.md |
| MLX не обрабатывает задачи (только Ollama) | ai_core.run_smart_agent_async создавал новый LocalAIRouter на каждый вызов → игнорировались _preferred_source/_preferred_model воркера | Использовать _current_router (с предпочтениями воркера), если передан; после вызова сбросить _current_router. См. ai_core.run_smart_agent_async |
| Heartbeats не обновляют updated_at | Пул БД max_size=5 при 10 конкурентных задачах + 10 heartbeats → нехватка соединений | Пул воркера: max(15, SMART_WORKER_MAX_CONCURRENT + 8) |
| «5 задач за час», 10 в работе | Зависшие in_progress сбрасывались раз в 1 ч → мало pending | SMART_WORKER_STUCK_MINUTES=15; непрерывный пул (семафор вместо ожидания всего батча) |
| Зависания/таймауты при вызове Ollama/MLX | В Docker LocalAIRouter игнорировал OLLAMA_API_URL/MLX_API_URL → узлы и сканер могли указывать на разные хосты | LocalAIRouter и сканер используют env; при отсутствии — host.docker.internal в Docker |
| Victoria возвращает ваш же текст (эхо) | Модель/сервер иногда возвращает промпт как ответ | _is_echo_response() в local_router; при эхо — следующий узел или None |
| Execution-задачи уходят в Veronica вместо экспертов | _should_delegate_task не учитывал PREFER_EXPERTS_FIRST | В victoria_enhanced при PREFER_EXPERTS_FIRST=true делегируем в Veronica только если _is_simple_veronica_request(goal); иначе остаётся Victoria/эксперты |
| Чат/стриминг к Victoria с пустым goal или неверным контрактом | VictoriaClient.run_stream отправлял "prompt" вместо "goal"; Victoria POST /run ожидает TaskRequest.goal | run() и run_stream() передают goal и project_context; при добавлении новых вызовов Victoria — сверять с TaskRequest в victoria_server |
| Конфликт имён Redis при запуске knowledge_os compose | Контейнер knowledge_redis уже занят проектом atra (отдельный репозиторий) | atra-web-ide использует свой Redis: контейнер **knowledge_os_redis**, порт хоста **6381**; в compose REDIS_URL=redis://redis:6379 (по имени сервиса); backend — redis://knowledge_os_redis:6379. Не менять обратно на knowledge_redis. См. PROJECT_ARCHITECTURE_AND_GUIDE.md |
| Порт 6380 уже занят при старте knowledge_os_redis | atra держит 6380:6379 для своего Redis | В knowledge_os/docker-compose.yml для redis задан порт **6381:6379**. При смене порта atra — можно вернуть 6380 только если atra не запущен на той же машине. |
| Счётчики «Завершено» / «за 15 мин» на дашборде не меняются после «Обновить» | (1) Кэш Streamlit: fetch_data_tasks с ttl=15 отдаёт старые данные; (2) дашборд и воркер смотрят в разные БД (разный DATABASE_URL); (3) воркер не завершает задачи (зависание на LLM, ошибка до UPDATE completed) | В дашборде: при нажатии «Обновить» — session_state.tasks_refresh_ts + st.cache_data.clear() + запросы с _cache_bust=refresh_ts (новый ключ кэша). Блок «Проверка БД» (expander): маскированный DATABASE_URL, сырые счётчики по статусам, последние 3 завершённые задачи (updated_at). Убедиться, что corporation-dashboard и knowledge_os_worker в одном compose используют один DATABASE_URL (knowledge_postgres:5432). Если в БД completed не растёт — смотреть логи воркера (Task … COMPLETED / marked completed in DB). См. knowledge_os/dashboard/app.py, вкладка «Автономные Задачи». |
| Зависание/таймауты при вызове тяжёлой модели (glm-4.7, qwen2.5-coder:32b) | **Не учтено время загрузки модели.** Ollama/MLX загружают модель при первом запросе (30–90 сек для тяжёлых). Запросы уходят до готовности модели → ReadTimeout, зависание. Модели — только из сканера; оркестратор может выбрать тяжёлую — но воркер не ждёт загрузки. | **Учитывать время загрузки и запас на развёртывание:** (1) перед отправкой блока задач к новой модели — проверять готовность модели (Ollama /api/ps, MLX /health/models); (2) или выдержка MODEL_LOAD_BUFFER_SEC (по умолчанию 60) после смены модели; (3) при SMART_WORKER_INTERLEAVE_BLOCKS=false — обрабатывать блоки последовательно и давать буфер перед первым запросом к новой модели. MLX уже ждёт загрузки (_loading_models); Ollama — нет, загрузка ленивая. См. WORKER_THROUGHPUT_AND_STUCK_TASKS.md, ADAPTIVE_WORKER_CONCURRENCY_PLAN.md. |
| Ollama возвращает `models: []` или 404 `model not found` | **Ollama запущен от другого пользователя.** Модели в `~/.ollama/` (per-user). Если `brew services start ollama` запущен от nik, а модели у bikos — сервер видит пустой каталог. | **Запуск от пользователя с моделями:** (1) `brew services stop ollama`; (2) `ollama serve` из терминала под нужным пользователем (bikos). Не запускать `brew services start ollama` — он может стартовать от другого пользователя. Проверка: `ps aux | grep ollama` — USER должен быть владелец ~/.ollama/models/. |
| MLX API падает с Metal assertion `Completed handler provided after commit call` | **Гонка в Metal/MLX** при высокой нагрузке: 5/5 параллельных запросов, переключение моделей (phi3.5 ↔ qwen2.5), одновременная генерация и загрузка другой модели. | **Снизить нагрузку:** MLX_MAX_CONCURRENT=3 (в scripts/start_mlx_api_server.sh или env). При повторных крашах — запуск: `bash scripts/start_mlx_api_server.sh`; логи: `tail -f ~/Library/Logs/atra/mlx_api_server.log`. system_auto_recovery.sh перезапускает MLX при недоступности. |
| MLX отдаёт 503 «Server overloaded» — запросы сверх лимита отклоняются | Раньше при достижении max_concurrent запрос сразу отклонялся (503). | **Очередь на сервере:** запрос ждёт свободный слот до MLX_QUEUE_WAIT_TIMEOUT (по умолчанию 120 с). Семафор ограничивает одновременную обработку; лишние запросы стоят в ожидании, затем обрабатываются. 503 только если слот не освободился за таймаут. |
| MLX API процесс завершается («Python завершила работу») | **Metal OOM:** GPU память исчерпана при тяжёлых промптах или нескольких запросах. В логах: `[METAL] Command buffer execution failed: Insufficient Memory (kIOGPUCommandBufferErrorOutOfMemory)` и `libc++abi: terminating`. | **Снизить нагрузку на GPU:** MLX_MAX_CONCURRENT=1 (по умолчанию в start_mlx_api_server.sh). Мониторинг: `scripts/monitor_mlx_api_server.sh` проверяет процесс и :11435/health каждые 30 с, перезапускает при падении (лимит 5/час). Настройка: `bash scripts/setup_system_auto_recovery.sh` — создаёт com.atra.mlx-monitor в launchd. См. MASTER_REFERENCE §5. |
| InvalidStateError в mlx_api_server при таймауте генерации | При таймауте (5 мин) вызывался result_future.set_exception(e), но Future уже отменён или завершён (wait_for отменил задачу). | **Проверка перед set_result/set_exception:** в _execute_generation вызывать set_result/set_exception только если `not result_future.done()`. Иначе — не трогать Future, только raise. См. knowledge_os/app/mlx_api_server.py. |
| Tacit Knowledge не применяется (стилевой профиль не подставляется) | is_coding_task использовался до определения → блок Tacit Knowledge никогда не выполнялся; или keywords слишком узкие | **Порядок в ai_core:** is_coding_task определяется ДО блока Tacit Knowledge. **Keywords:** расширены (напиши, создай, реализуй, api, endpoint и др.). См. ai_core.run_smart_agent_async. |
| Phase 1.5 декомпозиция падает с «column parent_task_id does not exist» | Миграция add_task_orchestration_schema.sql не применена | **Применить миграцию:** knowledge_os/db/migrations/add_task_orchestration_schema.sql. Оркестратор при ошибке skip phase 1.5 и продолжает; логи: «Phase 1.5 skipped: parent_task_id not in schema». |
| RAG отдаёт модели только «частички» (200 символов на узел) | В Victoria _get_knowledge_context каждый узел обрезался до 200 символов — модель не видела полного знания, польза ограничена. | **Настраиваемая длина и топ-1 полный:** RAG_SNIPPET_CHARS (по умолчанию 500), RAG_TOP1_FULL_MAX_CHARS (2000) — для топ-1 по similarity передаётся полный контент до лимита. Fallback ILIKE без usage_count: ORDER BY confidence_score DESC NULLS LAST, created_at DESC. См. victoria_server._get_knowledge_context. |
| В knowledge_nodes мало узлов с embedding — семантический поиск по малой доле | Раньше многие INSERT в knowledge_nodes без embedding; только часть узлов участвует в векторном поиске. | **При записи в knowledge_nodes:** по возможности вычислять и сохранять embedding (smart_worker_autonomous уже пишет embedding для отчётов задач). Остальные источники (оркестраторы, nightly, council) — при наличии semantic_cache/get_embedding вызывать и передавать embedding в INSERT. См. MASTER_REFERENCE § «Узлы знаний». |
| Стратегический вопрос в чате — ответ без «По решению Совета» или 503 | knowledge_rest (8002) недоступен; неверный API_KEY; таймаут board/consult (45 с); LLM в consult_board не ответил. | **Fallback:** чат при ошибке board/consult продолжает с Victoria без блока решения (уже реализовано). **Проверка:** KNOWLEDGE_OS_API_URL=http://knowledge_rest:8002 в backend; API_KEY в backend и knowledge_rest совпадают. Таблица board_decisions должна существовать (миграция add_board_decisions.sql). См. MASTER_REFERENCE §3б. |
| Save to cache error: expected 384 dimensions, not 768 | Схема БД (semantic_ai_cache/embedding_cache) была vector(384), а Ollama nomic-embed-text возвращает 768. | **Миграция:** fix_embedding_dimensions_768.sql (при старте Enhanced Orchestrator Phase 0.5 или вручную). **Код:** везде размерность 768: semantic_cache (EMBEDDING_DIM, проверка перед save), дашборд fallback, tacit_knowledge_miner, scout_researcher. VECTOR_CORE и дашборд: при 768-dim fallback совместимость с knowledge_nodes. См. CHANGES_FROM_OTHER_CHATS §0.1, MASTER_REFERENCE § эмбеддинги. |
| Veronica: «duckduckgo_search не установлен» | Пакет duckduckgo-search не в requirements или не установлен в образе воркера. | **Зависимость:** duckduckgo-search>=6.0.0 в knowledge_os/requirements.txt и корневом requirements.txt (образ агентов/воркера). После pip install -r requirements.txt или пересборки образа веб-поиск работает без предупреждения. См. CHANGES_FROM_OTHER_CHATS §0.1. |
| Ollama 500: «llama runner process has terminated», «failed to allocate context», MTLCompilerService | Ollama на хосте упал или Metal/GPU в плохом состоянии. **Почему происходит:** (1) **Конкуренция за Metal:** MLX (11435) и Ollama (11434) оба используют Metal на одном Mac; при одновременной нагрузке (воркер 5 задач → часть в MLX, часть в Ollama) MTLCompilerService может выдать «Reentrancy avoided» или «compiler is no longer active». (2) **Sleep/wake Mac:** после сна Metal-контекст может инвалидироваться. (3) **Нехватка контекста/памяти:** «failed to allocate context» при загрузке модели или смене модели под нагрузкой. Воркер получает HTTP 500 → задачи не завершаются. | **Перезапуск Ollama:** `brew services stop ollama`; `pkill -f ollama`; через 2–3 сек `ollama serve` из терминала. Проверка: `curl -s http://localhost:11434/api/tags`. **Снизить вероятность:** после sleep/wake перезапускать Ollama; при частых падениях — уменьшить SMART_WORKER_MAX_CONCURRENT или временно отключить MLX (только Ollama), чтобы не было одновременной нагрузки на Metal. Логи Ollama: `~/.ollama/logs/server.log`. |
| Одна и та же задача «ИССЛЕДОВАНИЕ: R&D» (и др.) появляется несколько раз в день у одного эксперта или у разных | Оркестраторы (Enhanced Phase 5, Streaming Curiosity) каждый цикл создавали новую задачу по «пустыне» без проверки: уже есть ли такая же задача (title+description) у этого эксперта за последние 30 дней. | **Дедупликация:** `task_dedup.same_task_for_expert_in_last_n_days(conn, title, description, assignee_expert_id, days=30)` перед INSERT. Enhanced: сначала `get_best_expert_for_domain`, проверка дубликата для этого эксперта, при наличии — skip. Streaming: перед INSERT проверка для выбранного assignee. Критерий: title + description + assignee_expert_id за 30 дней. См. CHANGES_FROM_OTHER_CHATS §0.2, knowledge_os/app/task_dedup.py. |
| **Очередь на ручную проверку** растёт (задачи с deferred_to_human) — «исчерпаны попытки автообработки или AI был недоступен» | Задача попадает в очередь после **3 неудачных попыток** (MAX_ATTEMPTS=3). Причины каждой неудачи: **(1) Все источники недоступны** — ai_core перебрал MLX, Ollama, cursor-agent — все вернули ошибку или таймаут (MLX/Ollama упали, Metal OOM, Ollama от другого пользователя, таймаут загрузки модели). **(2) Ответ LLM распознан как ошибка** — короткое сообщение с «недоступен», «Error», «failed» и т.п. **(3) Пустой/короткий ответ** — агент ничего не вернул или < 5 символов. **(4) Провал валидации** — task_result_validator отклонил ответ (score < 0.5). После 3 таких попыток rule_executor не справился → эскалация в Совет → задача завершена с deferred_to_human. | **Диагностика:** в metadata задачи и в дашборде (карточка «Ручная проверка») отображается **last_error** (timeout, текст исключения, empty_or_short_response). **Снижение вылетов:** перед повторной попыткой задержка **SMART_WORKER_RETRY_DELAY_SEC** (по умолчанию 90 с) — воркер не берёт задачу до истечения next_retry_after. **Устранить причину:** (1) Проверить MLX/Ollama: `curl -s http://localhost:11435/health`, `curl -s http://localhost:11434/api/tags`; при Metal OOM — MLX_MAX_CONCURRENT=1; (2) SMART_WORKER_LLM_TIMEOUT и LOCAL_ROUTER_LLM_TIMEOUT=300 (или 400 для тяжёлых моделей); (3) после устранения — кнопка «Вернуть в автообработку» сбрасывает deferred_to_human и attempt_count. См. CHANGES_FROM_OTHER_CHATS §0.3, §0.3k, smart_worker_autonomous (escalate_task_to_board). |
| **Часть задач не дожидается ответа** (сервера работают, но задачи уходят в ручную проверку) | **Внутренний HTTP-таймаут был короче, чем ожидание воркера.** Воркер ждёт до SMART_WORKER_LLM_TIMEOUT (300 с), но запрос к MLX/Ollama в local_router и ai_core был обрезан по **120 с** → под нагрузкой или на тяжёлых моделях ответ не успевал → таймаут → попытка неудачна. | **Исправлено:** таймаут запроса к узлам (MLX/Ollama) вынесен в env **LOCAL_ROUTER_LLM_TIMEOUT** (по умолчанию **300** с) в local_router и в ai_core (Ollama fallback). Воркер и роутер теперь ждут одинаково долго; при необходимости задать оба: SMART_WORKER_LLM_TIMEOUT=400 и LOCAL_ROUTER_LLM_TIMEOUT=400. См. local_router.py (POST к узлу), ai_core.py (Ollama fallback). |

---

## 4. Мировые практики (закреплённые)

- **Connection pooling**: один пул БД (db_pool), один HTTP-клиент (http_client) на процесс; лимиты (max_connections, keepalive). Воркер: пул достаточного размера для задач + heartbeats (max ≥ MAX_CONCURRENT + 8).
- **Graceful shutdown**: при остановке API вызывать close_http_client(), чтобы не оставлять висящие соединения.
- **Resilience**: при недоступности общего клиента — fallback (разовый AsyncClient); при невалидном кэше — повторный поиск, не падение.
- **Зависимости**: только в requirements.txt, установка при сборке/деплое, не в рантайме (12-Factor).
- **Тонкие обёртки**: db_pool, http_client, json_fast — единые точки замены при миграции на Rust или смене реализации.
- **Async: не блокировать event loop** (Backend/Performance): синхронный I/O (файлы, тяжёлые вычисления) в async-коде выполнять через run_in_executor; иначе heartbeats и другие корутины не выполняются → задачи считаются зависшими.
- **Воркер: heartbeat + таймаут** (SRE): длинные задачи обновляют updated_at (heartbeat), иначе монитор сбросит задачу; таймаут на вызов LLM (например 5 мин), чтобы не висеть бесконечно.

---

## 5. При следующих изменениях

- **Скрипты / другие модули:** при правках файлов в `knowledge_os/scripts/` или `knowledge_os/src/` заменять `datetime.utcnow()` на `datetime.now(timezone.utc)` (импорт `timezone` из `datetime`).
- **Новые FastAPI-приложения:** использовать `lifespan` (context manager), не `@app.on_event("startup")` / `@app.on_event("shutdown")`.
- **Новые тесты защищённых endpoint:** ожидать 401 при отсутствии токена, 403 — при нехватке прав (есть токен, но доступ запрещён).
- **Новый код в smart_worker_autonomous или цепочке воркера:** не вызывать синхронный I/O (open/read, requests.*, тяжёлые sync-функции) напрямую в async-функции; выносить в `run_in_executor`, иначе блокируется event loop и heartbeats.
- **Новый код, подключающийся к Ollama/MLX:** брать URL из env (OLLAMA_API_URL, MLX_API_URL); в Docker при отсутствии — host.docker.internal. См. [OLLAMA_MLX_CONNECTION_AND_ECHO.md](OLLAMA_MLX_CONNECTION_AND_ECHO.md).
- **Ollama: запуск после перезагрузки или смены пользователя:** модели в `~/.ollama/` (per-user). `brew services start ollama` может запустить сервер от другого пользователя (nik) — тогда `models: []`, 404. Решение: `brew services stop ollama`, затем `ollama serve` из терминала под пользователем с моделями (bikos). При настройке автозапуска — launchd-сервис от нужного пользователя или скрипт в system_auto_recovery.sh.
- **Изменения в делегировании Victoria → Veronica:** соблюдать PREFER_EXPERTS_FIRST: в Veronica только простые одношаговые запросы (_is_simple_veronica_request); «сделай/напиши код» — Victoria/эксперты. Проверять оба слоя: task_detector (src/agents/bridge) и _should_delegate_task (victoria_enhanced). См. [VERONICA_REAL_ROLE.md](VERONICA_REAL_ROLE.md).
- **Изменения в чате (backend → Victoria):** контракт Victoria POST /run — body.goal (не prompt), project_context опционально. VictoriaClient.run() и run_stream() должны передавать goal и project_context. При добавлении новых полей в запрос к Victoria — сверять с TaskRequest в victoria_server. См. пункт 21 чеклиста.
- **Новые источники создания задач от обучения (curiosity, nightly, dashboard_daily_improver):** перед INSERT проверять дубликат через `task_dedup.same_task_for_expert_in_last_n_days(conn, title, description, assignee_expert_id, days=30)`, если назначение эксперта известно до вставки. Критерий: одна и та же задача (title+description) для одного эксперта не чаще раза в 30 дней. См. CHANGES_FROM_OTHER_CHATS §0.2.
- **Внедрение авто-расчёта параллелизма воркера (адаптивный N):** реализовано в `adaptive_concurrency.py` и `smart_worker_autonomous.py`. При изменении — следовать [ADAPTIVE_WORKER_CONCURRENCY_PLAN.md](ADAPTIVE_WORKER_CONCURRENCY_PLAN.md): учёт CPU/памяти хоста, MLX и Ollama; лимиты по тяжёлым/лёгким моделям; пул БД по потолку `max(15, MAX_CONCURRENT + 8)`; метрики и обработка сбоев (OOM/таймауты → снижение N). Сверяться с Backend (пул, семафор), SRE (heartbeat, метрики), Performance (latency, backpressure).
- **Docker / Redis (atra-web-ide vs atra):** Redis — контейнер **knowledge_os_redis**, порт хоста **6381**. Не использовать имя контейнера knowledge_redis и порт 6380 (зарезервированы для atra). При добавлении сервисов в knowledge_os/docker-compose.yml проверять отсутствие конфликтов имён с atra. См. раздел 3 (причины сбоев) и [PROJECT_ARCHITECTURE_AND_GUIDE.md](PROJECT_ARCHITECTURE_AND_GUIDE.md).
- **MLX API: падения после перегрузки / Metal OOM:** (1) Metal assertion при переключении моделей — снизить MLX_MAX_CONCURRENT (по умолчанию 1 в start_mlx_api_server.sh). (2) Metal OOM (Insufficient Memory) — процесс завершается; мониторинг перезапускает: `scripts/monitor_mlx_api_server.sh` (проверка процесса и :11435/health каждые 30 с). Настройка один раз: `bash scripts/setup_system_auto_recovery.sh` (создаёт com.atra.mlx-monitor). Логи MLX: `tail -f ~/Library/Logs/atra/mlx_api_server.log`. См. раздел 3 (причины «MLX Metal OOM», «InvalidStateError при таймауте»).
- **Изменения в дашборде (Streamlit) или воркере задач:** дашборд и воркер должны подключаться к одной БД (один DATABASE_URL в compose для corporation-dashboard и knowledge_os_worker). При правках счётчиков «Завершено»/«В работе» сохранять принудительный сброс кэша при «Обновить» (_cache_bust) и блок «Проверка БД» для диагностики. См. раздел 3 (причина «Счётчики не меняются»).
- **Узлы знаний (knowledge_nodes) и RAG:** В БД хранится полный content; в контекст Victoria передаётся сниппет (RAG_SNIPPET_CHARS, по умолчанию 500) и при необходимости полный топ-1 (RAG_TOP1_FULL_MAX_CHARS). При добавлении записей в knowledge_nodes по возможности сохранять embedding для семантического поиска. **Размерность эмбеддингов:** везде 768 (nomic-embed-text); semantic_ai_cache, embedding_cache, knowledge_nodes — vector(768). Миграция fix_embedding_dimensions_768.sql при необходимости. Запросы к knowledge_nodes с большим content — использовать LEFT(content, N). См. раздел 3 (RAG частички, embedding, expected 384/768), MASTER_REFERENCE § «Узлы знаний».
- **Изменения в потоке Совет Директоров (чат → board/consult → Victoria):** при правках strategic_classifier, consult_board или chat router сохранять fallback: при ошибке/таймауте board/consult чат продолжает с Victoria без блока решения. API_KEY в backend и knowledge_rest должны совпадать. Таблица board_decisions (миграция add_board_decisions.sql) — поля session_id, user_id, source. См. пункт 36 чеклиста, MASTER_REFERENCE §3б.
- **Изменения в cache_normalizer_rs (Rust):** при правках `knowledge_os/cache_normalizer_rs` сохранять контракт с Python: `normalize_text(s)` = `' '.join(s.lower().split())`, `normalize_and_hash(s)` = MD5 hex нормализованной строки; батч `normalize_and_hash_batch(texts)` возвращает список хэшей в том же порядке. После правок: `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 cargo test` (при Python 3.14 в venv), проверка совместимости, бенчмарк `scripts/benchmark_cache_normalizer.py`. См. OPTIMIZATION_AND_RUST_CANDIDATES §4, пункт 26 чеклиста.
- **Решения по стратегии «корпорация на Rust»:** при добавлении новых Rust-модулей или смене приоритетов сверяться с [CORPORATION_RUST_ROADMAP.md](CORPORATION_RUST_ROADMAP.md): принципы (один контракт — одна замена, fallback, не трогать первыми оркестрацию/LLM), фазы, документирование в OPTIMIZATION_AND_RUST_CANDIDATES и обновление библии.

---

## 6. Ссылки

- **Релиз (2026-02-01):** [RELEASE_SPEED_OPTIMIZATION_2026-02-01.md](RELEASE_SPEED_OPTIMIZATION_2026-02-01.md)
- Оптимизации и кандидаты на Rust: [OPTIMIZATION_AND_RUST_CANDIDATES.md](OPTIMIZATION_AND_RUST_CANDIDATES.md)
- **Воркер: пропускная способность и зависания:** [WORKER_THROUGHPUT_AND_STUCK_TASKS.md](WORKER_THROUGHPUT_AND_STUCK_TASKS.md)
- **Авто-расчёт параллелизма воркера (CPU/память, MLX+Ollama, тяжёлые/лёгкие):** [ADAPTIVE_WORKER_CONCURRENCY_PLAN.md](ADAPTIVE_WORKER_CONCURRENCY_PLAN.md)
- **Ollama/MLX: подключение, зависания и эхо:** [OLLAMA_MLX_CONNECTION_AND_ECHO.md](OLLAMA_MLX_CONNECTION_AND_ECHO.md)
- Архитектура проекта: [PROJECT_ARCHITECTURE_AND_GUIDE.md](PROJECT_ARCHITECTURE_AND_GUIDE.md)
- Команда экспертов: [configs/experts/team.md](../configs/experts/team.md)

---

*Чеклист обновлён с учётом рекомендаций Backend (Игорь), QA (Анна), SRE (Елена). План «Speed without losing quality» завершён. Релиз выполнен 2026-02-01 (прогон + чеклист). Перед следующим релизом: прогнать тесты и пройти пункты раздела 1.*
