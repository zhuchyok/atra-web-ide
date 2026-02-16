# Единый справочник проекта ATRA Web IDE (Master Reference)

**«Библия» проекта** — это **этот документ + связка документов**, на которые он ссылается. Когда говорят **«библия»**, имеется в виду: изучить **docs/MASTER_REFERENCE.md** и при необходимости связанные документы (PROJECT_ARCHITECTURE_AND_GUIDE, ARCHITECTURE_FULL, CURRENT_STATE_WORKER_AND_LLM, WORKER_THROUGHPUT, OLLAMA_MLX, VERIFICATION_CHECKLIST, CHANGES_FROM_OTHER_CHATS, DASHBOARDS_AND_AGENTS_FULL_PICTURE, план верификации в .cursor/plans и др.). Закреплено в **.cursorrules** (раздел «Библия проекта»).

**Назначение:** при любых вопросах по разработке, изменениям, архитектуре, логике, портам, компонентам — **ищем здесь**. При добавлении нового или смене подхода — **отражаем здесь**. Документ всегда актуален.

**Обновлено:** 2026-02-14

Последние изменения (2026-02-14): **Singularity 14.0: Cognitive Dominance (14/10).** (1) Внедрен `UI/UX Audit Agent` (Vision-to-Code Auditor) для визуальной оценки интерфейсов по стандартам Apple HIG и Material Design. (2) Реализована система `Dynamic Expert Hiring` — автономный найм новых экспертов при обнаружении пробелов в знаниях. (3) Внедрена `Hierarchical Memory` с механизмом архивации неактивных знаний и «тенями» для их реанимации. (4) База знаний дополнена стандартами проектирования `UX_STANDARDS.md`.
Последние изменения (2026-02-14): **Singularity 13.0: Intelligence Synthesis (13/10).** (1) Внедрен `Recursive Self-Distillation Loop` (DeepSeek pattern) для самообучения на основе `interaction_logs`. (2) Создан `DistillationEngine` для извлечения выученных правил и анти-паттернов из опыта. (3) Реализована динамическая инъекция выученных правил в системные промпты через `ai_core.py`. (4) Цикл самообучения интегрирован в `Nightly Learner` для автономного развития мудрости системы.
Последние изменения (2026-02-14): **Singularity 12.0: Absolute Autonomy (12/10).** (1) Внедрен `AutonomousToolCreator` для генерации и регистрации новых навыков на лету при нехватке инструментов. (2) Реализован `MCTSPlanner` для древовидного планирования с симуляцией исходов (OpenAI o3 pattern). (3) Активирован `AutonomousSentinel` — проактивный «страж» для авто-исправления ошибок и мониторинга 24/7. (4) Внедрена `Episodic Memory` в `episodic_memory.py` для хранения персональных предпочтений и опыта взаимодействия. (5) Реализован `Multi-Agent Debate V2` в `multi_agent_debate.py` для консилиума моделей при решении критических задач. (6) Оптимизирован `Predictive Prefetching` в `semantic_cache.py` для упреждающего прогрева GraphRAG. (7) Внедрен `Deep Reasoning Channel` (OpenAI o3 pattern) в `extended_thinking.py` для разделения внутренних раздумий и финальных ответов. (8) Реализован `PersonalityManager` (Anthropic pattern) для динамической адаптации тона агента под контекст запроса. (9) Внедрен **Victoria Operator**: Вероника получила «глаза и руки» через `browser-use` и Playwright для автономного тестирования UI/UX. (10) Все предыдущие планы по Sandboxes, GraphRAG и Self-Evolution полностью закрыты и интегрированы.
Последние изменения (2026-02-14): **Singularity 10.0: Высокопроизводительный инференс (vLLM Level).**
Последние изменения (2026-02-14): **Singularity 10.0: Глобальный GraphRAG и Multi-Hop Reasoning.** (1) Внедрен `GraphRAGService` для глубокого поиска по графу знаний. (2) Реализована экстракция сущностей (`EntityExtractor`) и детекция сообществ (`CommunityDetector`). (3) Внедрен `MultiHopRetriever` для поиска логических цепочек (hops) между узлами. (4) AI Core переведен на гибридный режим: векторный поиск + графовое рассуждение.
Последние изменения (2026-02-14): **Singularity 10.0: Кросс-контейнерная самодиагностика и авто-изоляция.** (1) Внедрен `ContainerMetricsCollector` для мониторинга ресурсов в реальном времени. (2) Реализован `ContainerAnomalyDetector` на базе Z-score для выявления 'агрессоров'. (3) Создан `ContainerIsolationManager` для автоматического карантина и троттлинга подозрительных микросервисов. (4) В Дашборд добавлена панель управления здоровьем контейнеров с кнопками экстренной изоляции.
Последние изменения (2026-02-14): **Singularity 10.0: Реальные Docker-песочницы (Sandbox-as-a-Service).** (1) Внедрен `SandboxManager` для управления изолированными контейнерами экспертов (256MB RAM, 0.5 CPU). (2) `ReActAgent` перенаправляет `run_terminal_cmd` в песочницы. (3) Создан API роутер `sandbox.py` и оживлен Дашборд (реальный статус контейнеров и сброс среды). (4) Настроена общая папка `sandbox_shared` для обмена файлами.
Последние изменения (2026-02-14): **Singularity 10.0: Эффективность правок кода (Smart Patch).** (1) Внедрен инструмент `smart-patch` (SEARCH/REPLACE XML блоки) в `react_agent.py` для точечного редактирования файлов. Это заменяет полную перезапись JSON-строками, экономя токены и предотвращая ошибки экранирования. (2) Обновлены системные промпты экспертов: добавлен принцип «ЭФФЕКТИВНОСТЬ ПРАВОК (Aider)» и описание нового инструмента. (3) Создан скилл `smart-patch` в `knowledge_os/app/skills/smart-patch/`. (4) Верификация: запущен критический тест замены компонентов в `docker_log_monitor.py`.

Последние изменения (2026-02-14): **Phase 5: Advanced Orchestration Patterns.** (1) **Adaptive Pruning** — умная обрезка контекста. (2) **Red Team Critic** — аудит планов. (3) **Execution Optimizer** — параллельный запуск. (4) **AOI System** — автономная балансировка. (5) **AIP Protocol** — авто-внедрение. (6) **Tactical War Room** — экстренное реагирование экспертов. (7) **Expert Evolution** — интерфейс прокачки агентов.

Последние изменения (2026-02-15): **Victoria Telegram Bot: Health Check, Supervisor, Monitoring & Fast Track.** (1) В `victoria_telegram_bot.py` внедрена система пульса. (2) В `victoria_server.py` добавлены API эндпоинты `/health/telegram` и `Fast Track` роутинг для мгновенных ответов через `lfm2.5-thinking:1.2b`. (3) Создан `scripts/victoria_bot_supervisor.sh` с защитой от дублей. (4) В `prometheus_metrics.py` добавлены метрики `telegram_bot_*`. (5) В `executor.py` добавлена поддержка динамической смены модели. См. CHANGES §13.

Последние изменения (2026-02-14): **Phase 4: Dual-Channel Reasoning & Semantic History.**
Последние изменения (2026-01-28): **PRINCIPLE_EXPERTS_FIRST уровень «пушка».** (1) П.6: web_search_fallback — конфиг WEB_SEARCH_PROVIDERS, ретраи с экспоненциальной задержкой, таймауты по провайдеру, лог used_source. (2) П.1: кэш веб-результатов по хешу (WEB_SEARCH_CACHE_TTL_SEC, WEB_SEARCH_CACHE_MAX_SIZE); воркер пишет had_web_block в metadata задачи; метрика knowledge_os_tasks_web_block_total в /metrics. (3) П.2: выбор до 3 скиллов по релевантности к задаче (_select_skills_by_relevance_sync по keywords/description из SKILL.md). (4) П.4: backend /metrics/summary — числовые chat_expert_answer_total, chat_fallback_total, chat_fallback_ratio, alert_fallback_high (порог 30%); виджет в дашборде Knowledge OS при ATRA_BACKEND_URL; запись в VERIFICATION §3 про алерт при доле fallback > 30%. (5) П.7: при «Принять кандидата» — задача онбординга (assignee Виктория), запись в notifications (Telegram). PRINCIPLE_EXPERTS_FIRST.md обновлён (таблица «Реализовано», «Что можно усилить дальше»). См. CHANGES §0.4fc.
Последние изменения (2026-02-14): **Phase 2.6: Разделение воркеров по ролям (Heavy/Light).** Воркеры разделены на два типа: `expert-worker-heavy` (1 инстанс, модель `qwen3-coder:30b` для кода и архитектуры, лимит 10GB RAM) и `expert-worker-light` (2 инстанса, модель `lfm2.5-thinking:1.2b` для быстрых задач, лимит 4GB RAM). Это обеспечивает баланс между мощностью интеллекта и скоростью обработки простых запросов без перегрузки Mac Studio.
Последние изменения (2026-02-14): **Phase 2.5: Гибридное масштабирование и оптимизация RAM.** Количество реплик `expert-worker` снижено до 3 для уменьшения Swap на Mac Studio. Внедрена гибридная модель: лимиты памяти оптимизированы (6GB limit / 2GB reservation), включен `SMART_WORKER_MAX_CONCURRENT=2` для предотвращения взрывной нагрузки. Проведена полная очистка Docker ресурсов (reclaimed 17.91GB).
Последние изменения (2026-02-14): **Phase 2 Roadmap: Exponential Learning — Масштабирование и коллективное обучение.** В `knowledge_os/docker-compose.yml` воркер `expert-worker` масштабирован до 3 реплик (`deploy: replicas: 3`) для параллельной обработки задач. Включена система Collective Learning (`ENABLE_COLLECTIVE_LEARNING=true`): воркеры обмениваются опытом через `CorporationSelfLearning`, анализируя ошибки и оптимизируя выбор моделей в реальном времени. Исправлена ошибка сериализации `metadata` в `knowledge_service.py` (принудительный `json.dumps`). Верифицирован параллельный захват задач из Redis Stream.
Последние изменения (2026-02-14): **Оптимизация ресурсов и систематизация логов.** Проведена полная очистка логов Docker и локальных файлов (`./logs/*.log`). Во всех `docker-compose.yml` (корень и `knowledge_os/`) настроена принудительная ротация логов: `max-size: 10m`, `max-file: 3`. Все контейнеры перезапущены с `--force-recreate` для применения лимитов. Создан скрипт `scripts/maintenance/cleanup_logs.sh` для регулярного обслуживания. Это предотвращает критическую нагрузку на память и своп Mac Studio.
Последние изменения (2026-02-13): **Victoria: «Монстр-Логика» делегирования, фикс роутера и отказоустойчивость.** В `victoria_server.py`: принудительное выполнение `execute_assignments_async`, если назначено >1 эксперта (даже при наличии Вероники); `load_dotenv()` при старте; фикс путей `ko_paths` (добавлен `os.getcwd()`) и `sys.path` (локальный `_sys`); параметр `use_enhanced` в `TaskRequest`. В `intelligent_model_router.py`: реализован `estimate_task_complexity` (оценка сложности по промпту) и `get_pool` (DB pool). В `extended_thinking.py`: отказоустойчивость — одновременная попытка MLX и Ollama. В `integration_bridge.py`: принудительное назначение Вероники (coding) и Романа (DB) в V2. См. CHANGES §0.4fb.
Последние изменения (2026-02-08): **Victoria: 202 до стратегии, прогрев, OLLAMA_KEEP_ALIVE, кэш understand_goal.** При async_mode=true POST /run сразу возвращает 202; стратегия и understand_goal выполняются в фоне в _run_task_background. Прогрев при старте (warmup_victoria в lifespan при VICTORIA_WARMUP_ENABLED). OLLAMA_KEEP_ALIVE по умолчанию 86400 в docker-compose. GET /run/status при clarify в фоне отдаёт clarification_questions в корне ответа. Кэш _understand_goal_cache (TTL 300 с, макс. 200). См. CHANGES §0.4er, CURATOR_RUNBOOK §1.6.
Последние изменения (2026-02-11): **Proverka:** сверка с MASTER_REFERENCE и VERIFICATION_CHECKLIST_OPTIMIZATIONS §5. Затронутые области: куратор (run_curator_and_compare.sh — ensure Victoria перед прогоном; curator_send_tasks_to_victoria.py — таймаут POST 120 с, повторы при «timed out»; CURATOR_RUNBOOK §1.6 причина Read timed out). Пункт §5 «Запуск долгих скриптов»: таймаут среды ≥10/30 мин в runbook учтён. Тесты: run_all_system_tests **65 backend + 44 knowledge_os = 109 passed**. См. CHANGES §0.4ep, §0.4eo.
Последние изменения (2026-02-11): **План «Логика мысли» Victoria — Фаза 5 внедрена.** Интеграция и верификация: сквозные тесты (test_reasoning_logic_recap.py — ReCAP рефлексия; test_reasoning_logic_contract.py — контракт clarify/decline/strategy/confidence); обновлены VICTORIA_TASK_CHAIN_FULL (схема стратегия→память→план→выполнение→рефлексия→ответ с confidence, §9 тесты) и THINKING_AND_APPROACH (§6 Victoria). План полностью внедрён (фазы 0–5). См. CHANGES §0.4eo.
Последние изменения (2026-02-11): **Proverka:** сверка с MASTER_REFERENCE и VERIFICATION_CHECKLIST_OPTIMIZATIONS §5; затронутые области (Victoria, ReCAP, long_term_memory, victoria_common, маршрутизация, чат) проверены по чеклисту. Тесты: run_all_system_tests 106 passed, test_task_detector_chain 20 passed. Пункт 38 учтён (при деплое — пересборка victoria-agent, куратор при необходимости). См. CHANGES §0.4en.
Последние изменения (2026-02-11): **План «Логика мысли» Victoria — Фаза 4 внедрена.** Неопределённость в контракте: при confidence < 0.7 в knowledge добавляется uncertainty_reason (из стратегии или reason); в _select_strategy planner может вернуть uncertainty_reason. Промпты: PROMPT_UNCERTAINTY_LINE и пункт 7 в build_simple_prompt — явно выражать неопределённость в ответе. См. CHANGES §0.4em.
Последние изменения (2026-02-11): **План «Логика мысли» Victoria — Фаза 3 внедрена.** Рефлексия и пересмотр плана в ReCAP: после провала/пустого шага вызов _should_revise_plan (ДА/НЕТ + причина); при «ДА» — пересборка плана с контекстом previous_plan_failure, лимит VICTORIA_MAX_PLAN_REVISIONS (1). VICTORIA_REFLECTION_ENABLED, VICTORIA_MAX_PLAN_REVISIONS в docker-compose и .env.example. См. CHANGES §0.4el, VICTORIA_TASK_CHAIN_FULL §5.3.
Последние изменения (2026-02-11): **План «Логика мысли» Victoria — Фаза 2 внедрена.** Долгосрочная память: таблица long_term_memory (миграция add_long_term_memory.sql), менеджер long_term_memory.py (save_thread, get_recent_threads); после успешного ответа сохраняется резюме обмена, при запросе подмешивается блок «Ранее по этому проекту/пользователю» в контекст Enhanced. Объединение с session (task_memory) в одном контексте. LONG_TERM_MEMORY_ENABLED по умолчанию false. См. CHANGES §0.4ek, VICTORIA_TASK_CHAIN_FULL §5.2.
Последние изменения (2026-02-11): **План «Логика мысли» Victoria — Фаза 0 и Фаза 1 внедрены.** В Victoria добавлен единый слой выбора стратегии: _select_strategy (planner, кэш по goal+session_summary), стратегии quick_answer / deep_analysis / need_clarification / decline_or_redirect; ранний выход при clarification и decline; маршрутизация quick→Veronica/agent, deep→Enhanced; strategy/confidence в knowledge во всех путях ответа; async 202 после стратегии и understand_goal, _run_task_background с _inject_strategy и _save_session_exchange. Контракт в VICTORIA_TASK_CHAIN_FULL §5.1, промпты в PROMPTS_VICTORIA. Env: VICTORIA_STRATEGY_ENABLED, STRATEGY_CACHE_TTL_SEC в .env.example и knowledge_os/docker-compose. Тесты 106 passed. См. CHANGES §0.4ej.
Последние изменения (2026-02-11): **План «Логика мысли» Victoria.** Документ [PLAN_REASONING_LOGIC_VICTORIA.md](PLAN_REASONING_LOGIC_VICTORIA.md) — детальный план по внедрению единой линии рассуждения: выбор стратегии (quick/deep/clarify/decline), связность и память между диалогами, самокритика и итерация плана, неопределённость как часть логики. Опора на команду экспертов, базу знаний (session_context, query_classifier, task_detector, victoria_enhanced, recap, collective_memory) и мировые практики (MAR, ReCAP, LoCoMo, ограничения self-verification). Фазы 0–5 с задачами и критериями. См. CHANGES §0.4ei.
Последние изменения (2026-02-08): **Proverka:** сверка с MASTER_REFERENCE и VERIFICATION §5; тесты run_all_system_tests 106 passed, test_task_detector_chain 20 passed. См. CHANGES §0.4eh.
Последние изменения (2026-02-08): **Планы закрыты:** всё запланированное внедрено; TODO_FIXME_BACKLOG (высокий/средний) закрыт; планы «умнее быстрее», «как я», PRINCIPLE_EXPERTS_FIRST, бэклог — закрыты. Планы можно считать закрытыми. См. CHANGES §0.4eg.
Последние изменения (2026-02-08): **Proverka полная (даже мелкие):** сверка с MASTER_REFERENCE и VERIFICATION §5 по всем затронутым областям (чат, Victoria, оркестрация, веб-поиск, стратегия/планы, RAG, уведомления, долгие скрипты); тесты run_all_system_tests 106 passed, test_task_detector_chain 20 passed; таймаут куратора (≥10/30 мин) в runbook; границы SRC_AND_KNOWLEDGE_OS и 12-Factor учтены. См. CHANGES §0.4ef.
Последние изменения (2026-02-08): **«Дальше делай что осталось»:** в web_search_fallback добавлен fallback на Ollama web_search при OLLAMA_API_KEY (POST ollama.com/api/web_search). П.6 PRINCIPLE_EXPERTS_FIRST завершён. См. CHANGES §0.4ee.
Последние изменения (2026-02-08): **«Делай дальше все»:** реализованы четыре пункта TODO_FIXME_BACKLOG: master_plan_generator (update_master_plan + get_plan/update_plan в session_manager), strategy_discovery (LLM уточняющие вопросы), model_enhancer (pgvector в retrieve_enhanced_context), early_warning_system (Telegram/Email уведомления). Тесты 106 passed. См. CHANGES §0.4ed.
Последние изменения (2026-02-08): **Proverka:** сверка с MASTER_REFERENCE и VERIFICATION_CHECKLIST_OPTIMIZATIONS §5; затронутые области (оркестрация, Victoria, тесты) проверены по чеклисту; запущен run_all_system_tests — 62 backend + 44 knowledge_os = 106 passed. См. CHANGES §0.4ec.
Последние изменения (2026-02-11): **«Всё доделывай»:** hierarchical_orchestration — генерация через модель (Ollama в _decompose_goals, парсинг, fallback); query_orchestrator — подбор из БД в select_context (enrich_context_from_db_async по goal); ORCHESTRATION_CANARY — как включить V2 100%; TODO_FIXME_BACKLOG обновлён. См. CHANGES §0.4eb.
Последние изменения (2026-02-11): **Proverka:** сверка с MASTER_REFERENCE и VERIFICATION §5; в четырёх планах отмечены закрытые пункты (п. 1.2 сохранение обмена в плане «как я»); остальные пункты бэклога — по TODO_FIXME_BACKLOG при касании. См. CHANGES §0.4ea.
Последние изменения (2026-02-11): **«Погнали»:** куратор при деплое — CURATOR_RUNBOOK §1.5, scripts/run_curator_post_deploy.sh, HOW_TO_INDEX; TODO_FIXME_BACKLOG: recap_framework — реальные результаты зависимостей в _build_context (results). См. CHANGES §0.4dz.
Последние изменения (2026-02-11): **«Доделываем»:** чекпоинт П.1.2 — сессия закрыта; тесты 103 passed. См. CHANGES §0.4dy.
Последние изменения (2026-02-11): **«Дальше»:** план «как я» П.1.2 — после каждого успешного ответа Victoria при наличии session_id вызывается _save_session_exchange (goal, output) в session_context_manager (четыре пути: quick_data, veronica, enhanced, agent_run). См. CHANGES §0.4dx.
Последние изменения (2026-02-11): **«Дальше по плану»:** план «умнее быстрее» §3.1 эталоны куратора — в _get_curator_rag_context добавлены list_files, greeting, one_line_code по ключевым словам (RAG curator_standards). См. CHANGES §0.4dw.
Последние изменения (2026-02-11): **«Дальше»:** план «умнее быстрее» §4.1 Nightly → видимость в RAG — скрипт backfill_knowledge_embeddings.py для дозаписи embedding узлам knowledge_nodes без него (Ollama get_embedding). HOW_TO_INDEX дополнен. См. CHANGES §0.4dv.
Последние изменения (2026-02-11): **«Двигаемся дальше»:** план «умнее быстрее» §2.1 «сделай как тогда» — при фразах «как вчера»/«повтори» перед understand_goal подставляется контекст последних завершённых задач из БД (recent_tasks_context.py, victoria_server). См. CHANGES §0.4du.
Последние изменения (2026-02-11): **Proverka «все делаем»:** сверка с MASTER_REFERENCE и VERIFICATION §5; в четырёх планах отмечены закрытые пункты; тесты run_all_system_tests. См. CHANGES §0.4dt.
Последние изменения (2026-02-11): **«Погнали дальше по планам»:** план «как я» п.11.3 п.1 — в victoria_enhanced все промпты «русский + краткость» из configs.victoria_common; §3.1 для execution/multi_step при simple уже реализован. См. CHANGES §0.4ds.
Последние изменения (2026-02-11): **«Сделай сама»:** исполнение по assignments включено по умолчанию (EXECUTE_ASSIGNMENTS_IN_RUN=true в docker-compose victoria-agent) — план оркестратора выполняется без ручной настройки. См. CHANGES §0.4dr.
Последние изменения (2026-02-11): **«Погнали дальше»:** в планах закрыты пункты: умнее быстрее §1.1 (стратегия 128 GB в гайде), §3.1 (RAG usage_count DESC); как я п.1.1 (вариант A «план = подсказка» принят), п.2 (fallback greeting/what_can_you_do уже в коде). См. CHANGES §0.4dq.
Последние изменения (2026-02-11): **Proverka:** сверка с MASTER_REFERENCE и VERIFICATION §5; планы (бэклог, PRINCIPLE_EXPERTS_FIRST, умнее быстрее, как я) проверены; в плане «как я» п.3.1 отмечено дополнение --write-findings в run_curator_and_compare.sh. Тесты 103 passed. См. CHANGES §0.4dp.
Последние изменения (2026-02-11): **«Дальше делаем»:** run_curator_and_compare.sh поддерживает --write-findings (и --full --write-findings); при регулярном прогоне FINDINGS пополняются автоматически. CURATOR_RUNBOOK §2 дополнен. См. CHANGES §0.4do.
Последние изменения (2026-02-11): **«Делаем дальше» §4.1:** candidate for standard (при лайке инсайт с metadata.suggested_standard=true); куратор с --write-findings пишет в FINDINGS_YYYY-MM-DD при падении скоринга по релевантным задачам; CURATOR_RUNBOOK §2–3 обновлён. См. CHANGES §0.4dn.
Последние изменения (2026-02-11): **Proverka:** сверка с библией и VERIFICATION §5; тесты 103 passed; планы сверены — новых пунктов для закрытия нет. См. CHANGES §0.4dm, §0.4dl.

Последние изменения (2026-02-11): **«Доделываем»: контекст 64k–128k и блок экспертов в simple.** В MAC_STUDIO_M4_MODELS_GUIDE добавлены рекомендации по env для длинного контекста (VICTORIA_HISTORY_MAX_CHARS, VICTORIA_CHAT_HISTORY_MAX_MESSAGES). В victoria_enhanced для status_query/general в simple подмешивается строка «Ответ в духе команды: дашборд, MASTER_REFERENCE, эксперты Backend/QA/SRE/ML». Планы обновлены. См. CHANGES §0.4dk.

Последние изменения (2026-02-11): **Proverka «делаем все»: §4 обратная связь «принять».** При лайке в POST /api/feedback инкрементируется usage_count для узлов из metadata.knowledge_node_ids (interaction_logs); LogInteractionRequest принимает knowledge_node_ids для сохранения при логировании. План «умнее быстрее» §4 отмечен выполненным. См. CHANGES §0.4dj.

Последние изменения (2026-02-11): **Proverka: закрытие пунктов в планах.** В планах «умнее быстрее», «как я», бэклог, PRINCIPLE_EXPERTS_FIRST отмечены сделанные пункты (§3.1 runbook по типу задачи, п. 3.1 run_curator_and_compare, п. 11.3 PROMPTS_VICTORIA.md и др.); обновлены «Следующие шаги». Тесты: 103 passed. См. CHANGES §0.4di.

Последние изменения (2026-02-11): **«Все делаем»: runbook по типу задачи, промпты Victoria, куратор.** (1) По плану «умнее быстрее» §3.1: для категорий coding/execution/informational/reasoning в simple-промпт подмешивается блок «По runbook и чеклисту» из knowledge_nodes (домен curator_standards или metadata.runbook=true). (2) Документ **docs/PROMPTS_VICTORIA.md** — таблица промптов (где, откуда, владелец). (3) **scripts/run_curator_and_compare.sh** — прогон куратора + сравнение по всем эталонам; в CURATOR_RUNBOOK §2 добавлена ссылка. См. CHANGES §0.4dh.

Последние изменения (2026-02-11): **Учёт таймаута среды везде.** Правило «timeout среды ≥ требуемому времени скрипта» закреплено в VERIFICATION §3 (причина сбоя), §4 (практика), §5 (при запуске долгих скриптов); в docstring куратора; в CONTRIBUTING, proverka, HOW_TO_INDEX, .cursorrules. Новые долгие скрипты — указывать в docstring/runbook рекомендуемый timeout. См. CHANGES §0.4dg.

Последние изменения (2026-02-11): **Причина таймаута куратора.** Таймаут при прогоне куратора вызван внешним лимитом среды (например 3 мин), а не внутренним poll timeout. При --quick нужно не менее 8–10 мин (2 задачи × до 180 с + холодный старт). CURATOR_RUNBOOK §1 дополнен; см. CHANGES §0.4df.

Последние изменения (2026-02-11): **Proverka: закрытие сделанных пунктов в планах.** В планах «умнее быстрее» и «как я» отмечены как закрытые: understand_goal на умной модели, длинный контекст, runbook Veronica; память по задаче, шаблон simple, контекст из БД «задачи по проекту». Обновлены блоки «Следующие шаги». См. CHANGES §0.4de.

Последние изменения (2026-02-11): **Планы «умнее быстрее» и «как я»: длинный контекст, память по задаче, шаблон simple.** Длинный контекст: VICTORIA_CHAT_HISTORY_MAX_MESSAGES, VICTORIA_HISTORY_MAX_CHARS, VICTORIA_GOAL_MAX_CHARS в bridge. Память по задаче: get_session_memory_summary в session_context_manager; bridge передаёт task_memory при session_id; в Enhanced блок «По этой сессии уже делали». Шаблон simple: build_simple_prompt и WORLD_PRACTICES_LINE в configs/victoria_common. См. CHANGES §0.4dd.

Последние изменения (2026-02-11): **Контекст из БД: задачи по проекту в промпт Victoria.** При наличии project_context в context для Enhanced подмешивается блок «Текущие задачи по проекту» (до 5 последних из tasks по project_context). Bridge передаёт project_context в context_with_history; victoria_enhanced._get_project_tasks_context запрашивает БД и добавляет блок в simple-промпт. См. CHANGES §0.4dc.

Последние изменения (2026-02-11): **Планы: закрыты сделанные пункты.** В четырёх планах (.cursor/plans/) отмечено выполненное (PRINCIPLE_EXPERTS_FIRST — все 7 пунктов; бэклог — целиком; «умнее быстрее» и «как я» — соответствующие блоки) и перечислены следующие шаги. См. CHANGES §0.4db.

Последние изменения (2026-02-11): **PRINCIPLE_EXPERTS_FIRST: П.3–П.7.** П.3: POST /api/feedback — при лайке инсайт в knowledge_nodes. П.4: метрики chat_expert_answer_total / chat_fallback_total в backend. П.5: маркеры критично/urgent → Swarm в Victoria. П.6: web_search_fallback.py — единая точка веб-поиска. П.7: GET/POST /api/recruitment/candidates и кнопка «Принять кандидата» в дашборде. См. CHANGES §0.4da.

Последние изменения (2026-02-11): **PRINCIPLE_EXPERTS_FIRST Фаза 1: скиллы и веб-поиск в воркере.** В smart_worker_autonomous: (1) П.2 — по role/department подставляются 1–2 скилла из app/skills/ (SKILL.md до 2 KB) в блок «ИНСТРУКЦИИ ИЗ СКИЛЛОВ»; чтение файлов через run_in_executor. (2) П.1 — при маркерах актуальности в задаче (2025, best practices, последние и т.д.) один раз веб-поиск (DuckDuckGo) через run_in_executor, таймаут 10 с, топ-3 сниппета в блок «АКТУАЛЬНЫЕ ДАННЫЕ ИЗ ВЕБ-ПОИСКА». См. CHANGES §0.4cz.

Последние изменения (2026-02-11): **Embedding при вставке в knowledge_nodes — все пути доделаны.** Добавлено сохранение embedding в streaming_orchestrator, strategic_board (2), dashboard_daily_improver, expert_council_discussion, expert_evolver, researcher, expert_generator, process_expert_task, ad_generator, meta_synthesizer, knowledge_bridge. Все пути записи в app/ и observability/ по возможности сохраняют embedding. См. CHANGES §0.4cy.

Последние изменения (2026-02-11): **Embedding при вставке в knowledge_nodes — все пути.** Добавлено сохранение embedding в nightly_learner (3 места), knowledge_applicator, skill_discovery, enhanced_orchestrator. Все перечисленные в WHATS_NOT_DONE §4 пути записи по возможности сохраняют embedding. См. CHANGES §0.4cx.

Последние изменения (2026-02-11): **Embedding при вставке в knowledge_nodes: orchestrator, enhanced_expert_evolver.** По возможности сохраняется embedding (get_embedding из semantic_cache) при записи кросс-доменной гипотезы и события эволюции эксперта. См. CHANGES §0.4cw.

Последние изменения (2026-02-11): **Embedding при создании знания через REST API.** В rest_api.py POST /knowledge по возможности сохраняется embedding (get_embedding из semantic_cache, content[:8000]); при недоступности — узел создаётся без embedding. См. CHANGES §0.4cv.

Последние изменения (2026-02-11): **Сессия «надо всё сделать».** Покрытие CI поднято до 8%; WHATS_NOT_DONE — блок «Закрыто / Не делаем в этой сессии» и уточнение путей записи эмбеддингов в knowledge_nodes. См. CHANGES §0.4cu.

Последние изменения (2026-02-11): **Роль куратора-наставника и эталон list_files.** CURATOR_RUNBOOK §0: куратор не учит Victoria при каждой задаче, а держит эталоны и RAG; Victoria учится из контекста. Эталон list_files: в сравнение добавлены STDOUT/total для ответов через Veronica; задача «список файлов» даёт 2/6 ключевых фраз. См. CHANGES §0.4ct.

Последние изменения (2026-02-11): **Чекпоинт сессии: планы «как я» и «умнее, быстрее» внедрены, верификация.** Прогнаны тесты: backend 62 + knowledge_os 41 = 103 passed, test_task_detector_chain 20 passed. В VERIFICATION_CHECKLIST добавлен п.38 (после правок Victoria/Enhanced — run_all_system_tests, пересборка образа, при необходимости куратор); в run_all_system_tests.sh — использование knowledge_os/.venv при наличии pytest. REDIS_URL добавлен в docker-compose для victoria-agent. При следующем поднятии стека рекомендуется быстрый прогон куратора (CURATOR_RUNBOOK §3). Дальше по плану: куратор при деплое, при желании — пункты из TODO_FIXME_BACKLOG. См. CHANGES §0.4cs.

Последние изменения (2026-02-10): **RAG-кэш в Redis (план «дальше»).** В victoria_server добавлен RAG_CACHE_BACKEND=memory|redis; при redis кэш контекста RAG в Redis (ключ rag_ctx:{md5(goal)}, TTL из RAG_CACHE_TTL_SEC, REDIS_URL). По умолчанию memory. NEXT_STEPS §2 обновлён. См. CHANGES §0.4cr.

Последние изменения (2026-02-10): **Планы «как я» и «умнее, быстрее» — вторая очередь.** (1) Контекст «ранее по задаче»: в промпте simple при наличии chat_history подпись заменена на «Ранее по задаче (контекст чата):». (2) RAG: в victoria_server._get_knowledge_context добавлена сортировка по **usage_count DESC NULLS LAST** (векторный и ILIKE fallback). (3) Похожие успешные решения: в victoria_enhanced добавлен _get_similar_tasks_context(goal) — до 2 записей из домена victoria_tasks, подставляются в промпт simple. (4) Runbook по типу задачи: в HOW_TO_INDEX строка и в KNOWLEDGE_BASE_USAGE §6 (curator_standards, victoria_tasks, usage_count, скрипт эталонов). (5) CURATOR_CHECKLIST: куратор как регрессия, candidate for standard при обратной связи «принять». См. CHANGES §0.4cq.

Последние изменения (2026-02-10): **Планы «как я» и «умнее, быстрее» — вторая очередь.** Контекст «ранее по задаче»: в промпте simple история чата подписана «Ранее по задаче (контекст чата):». RAG: в victoria_server._get_knowledge_context добавлена сортировка по usage_count DESC (векторный и ILIKE fallback). Похожие выполненные задачи: _get_similar_tasks_context в victoria_enhanced ищет по сходству цели (ILIKE) в домене victoria_tasks, приоритет usage_count; fallback — последние 2 по использованию. HOW_TO_INDEX: строка «Runbook по типу задачи». CURATOR_MENTOR_CAUSES: блок «Куратор как регрессия» и candidate for standard. См. CHANGES §0.4cq.

Последние изменения (2026-02-10): **Планы «как я» и «умнее, быстрее, знания в дело» — шесть пунктов внедрены.** (1) MAC_STUDIO_M4_MODELS_GUIDE: раздел «Стратегия быстрый + умный для 128 GB» (набор моделей, порядок загрузки, когда какую использовать). (2) Victoria Enhanced: при недоступности LLM — эталонные ответы для **greeting** и **what_can_you_do** (как для status_project), источник «что умеешь» — get_capabilities_text(). (3) CURATOR_RUNBOOK: §4 Veronica (таймауты DELEGATE_VERONICA_TIMEOUT, сбои «список файлов», ссылка CURATOR_LIST_FILES_FAILURES); §5 операционные «секретики» (таблица: один воркер, VERIFICATION §5, границы, Redis 6381, маршрутизация, контракт, recovery). (4) CONTRIBUTING: чеклист при коммите (тесты, куратор при необходимости, обновить MASTER_REFERENCE/CHANGES). (5) configs/victoria_common: PROMPT_RUSSIAN_ONLY и PROMPT_RUSSIAN_AND_BREVITY_LINES; victoria_enhanced (simple_prompt) и react_agent используют их. См. CHANGES §0.4cp.

Последние изменения (2026-02-10): **Куратор «все сделаем»:** повторный прогон (curator_2026-02-10_00-38-32), сравнение с эталонами (status_project по-прежнему 0/3), launchd включён (ежедневно 9:00, CURATOR_MAX_WAIT=900), обновлены FINDINGS, VERIFICATION, WHATS_NOT_DONE. Остаётся: проверить подтягивание RAG в enhanced для «статус проекта». См. CHANGES §0.4cd.

Последние изменения (2026-02-10): **Куратор «все делай»:** полный прогон (curator_2026-02-10_00-21-17), сравнение со всеми эталонами (greeting 5/5, what_can_you_do 8/9; status_project 0/3 — RAG узел обновлён), RAG --update-status, FINDINGS_2026-02-10 и VERIFICATION_2026-02-10. См. CHANGES §0.4cc.

Последние изменения (2026-02-10): **Куратор и эталоны: действия сейчас.** WHATS_NOT_DONE — блок «Действия сейчас (погнали)» (полный прогон куратора, при расхождении доучить RAG и standards/, эталон status_project, стабильность). Эталон status_project: короткая формулировка для RAG; скрипт curator_add_standard_to_knowledge.py — флаг --update-status для обновления узла в БД. CURATOR_RUNBOOK — расхождения, стабильность. См. CHANGES §0.4bz.

Последние изменения (2026-02-09): **MLX: стратегия «только лёгкие модели и жизнедеятельность».** Документ [MLX_STRATEGY_LIGHT_AND_VITALITY.md](MLX_STRATEGY_LIGHT_AND_VITALITY.md) — роль MLX не решение тяжёлых задач, а приветствия, короткие ответы, лёгкая классификация; тяжёлое — Ollama. В **mlx_api_server.py** при **MLX_ONLY_LIGHT=true** (по умолчанию) все категории (default, coding, reasoning) → **fast** (лёгкая модель), предзагрузка только fast. Правила Дмитрий/Елена обновлены; HOW_TO_INDEX — строка «MLX вылетает / как использовать». См. CHANGES §0.4bn.

Последние изменения (2026-02-09): **Осталось: линтер по путям, .env.example, e2e стратегия→board, куратор launchd.** CI: ruff только по изменённым .py (job lint в pytest-knowledge-os.yml). В корне добавлен **.env.example** (шаблон без секретов). E2E сценарий «стратегический вопрос → board → Victoria»: описание в TESTING_FULL_SYSTEM §2, скрипт `scripts/test_strategic_chat_e2e.sh`. Куратор по расписанию: `scripts/setup_curator_launchd.sh` (launchd, ежедневно 9:00), инструкция в CURATOR_RUNBOOK. См. CHANGES §0.4bi.

Последние изменения (2026-02-09): **Contributing Guide, E2E, TODO backlog, ручные проверки.** Создан **CONTRIBUTING.md** (запуск, тесты, E2E Playwright, методология, эксперты, развитие Victoria, TODO backlog). E2E документированы в TESTING_FULL_SYSTEM и HOW_TO_INDEX; запуск: `cd frontend && npm run e2e`. **TODO_FIXME_BACKLOG** обновлён: контекст по модулям среднего/низкого приоритета (hierarchical_orchestration, recap_framework, query_orchestrator, master_plan_generator, strategy_discovery, skill_discovery, model_enhancer, early_warning_system; signal_live, data_quality — ссылка на SIGNALS_TODO_REENABLE). Добавлен **docs/MANUAL_VERIFICATION_CHECKLIST.md** — чеклист ручных проверок (эхо/503, делегирование, Grafana Prometheus, launchd). См. CHANGES §0.4bh.

Последние изменения (2026-02-09): **Тяжёлые модели 70B/104B удалены из всех приоритетов (Apple Silicon Metal limits).** После повторных падений MLX с SIGABRT (Metal OOM: 27 GB buffer limit) **удалены из приоритетов** `deepseek-r1-distill-llama:70b`, `command-r-plus:104b`, `llama3.3:70b`: (1) `available_models_scanner.py` — `MLX_BEST_FIRST` и `MLX_PRIORITY_BY_CATEGORY` теперь max 32B (qwen2.5-coder:32b, phi3.5:3.8b); (2) `victoria_server.py` — hardcoded приоритеты для ml/security/reasoning/complex заменены на qwq:32b + qwen2.5-coder:32b (Ollama); (3) `mlx_api_server.py` — `_HEAVY_KEYS_NO_PRELOAD` оставляет только «reasoning» (не привязан к конкретным моделям). Victoria больше **не пытается загрузить 70B/104B → MLX стабилен**, если в MODEL_PATHS нет тяжёлых. См. CHANGES §0.4bd.

Последние изменения (2026-02-09): **При добавлении новой модели — замер холодного старта и занесение в библию.** Runbook: после добавления модели (Ollama pull или MLX MODEL_PATHS) обязательно запускать `measure_cold_start_all_models.py` (MEASURE_SOURCE=ollama|mlx); скрипт обновляет configs/ollama_model_timings.json или configs/mlx_model_timings.json; при необходимости обновить таблицу в MODEL_COLD_START_REFERENCE; учитывать recommended_timeout_sec в таймаутах (Victoria, backend, MLX). Так время загрузки и обработки учитывается при выполнении задач. §4 и MODEL_COLD_START_REFERENCE «Runbook: добавление новой модели»; HOW_TO_INDEX — строка «Добавление новой модели». См. CHANGES §0.4bc.

Последние изменения (2026-02-09): **Apple Silicon / Metal: лимиты перед добавлением тяжёлой модели.** На Mac с MLX действуют жёсткие лимиты Metal: (1) **общий лимит GPU-памяти — порядка 75% RAM** (recommendedMaxWorkingSetSize); (2) **лимит на один буфер — порядка 27 GB** (на M4 Pro; один тензор/матрица не может превышать). Модели 70B/104B при загрузке или длинном префилле могут превысить лимит → процесс падает (SIGABRT в mlx::core::gpu::check_error). **Перед добавлением тяжёлой модели в MLX:** проверить объём RAM машины и не добавлять в MODEL_PATHS модели, требующие больше ~75% RAM или один буфер >27 GB. Подробно: [MLX_PYTHON_CRASH_CAUSE.md](MLX_PYTHON_CRASH_CAUSE.md). См. CHANGES §0.4ba.

Последние изменения (2026-02-09): **«Мозги» корпорации в Victoria и Veronica (§0.4aw).** Логика из THINKING_AND_APPROACH вынесена в configs/corporation_thinking.txt и подставляется в промпт Victoria (блок «КАК МЫ МЫСЛИМ»); Veronica явно задана как «руки» — только исполнение шагов по плану; victoria_capabilities обновлён. См. CHANGES §0.4aw.

Последние изменения (2026-02-09): **Mac Studio: характеристики и загрузка (§0.4av).** Документ [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md) — RAM/Docker 8–12 GB, кто что потребляет, рекомендуемые переменные (MAX_CONCURRENT_VICTORIA 10–20, USE_ELK=false, async_mode); в docker-compose — комментарий и deploy.resources.reservations.memory для victoria-agent; в backend config и .env — ссылка на док; VICTORIA_RESTARTS_CAUSE и MAC_STUDIO_INDEX обновлены. См. CHANGES §0.4av.

Последние изменения (2026-02-09): **Стабильность Victoria при нагрузке (§0.4au).** Обработка исключений в фоновой задаче (done_callback, CancelledError, BaseException); рекомендация async_mode для длинных запросов; UVICORN_WORKERS; VICTORIA_RESTARTS_CAUSE §5. См. CHANGES §0.4au.

Последние изменения (2026-02-09): **Проверка корпорации пошагово (§0.4at).** Документ [CORPORATION_CHECK.md](CORPORATION_CHECK.md) — что проверяем (эксперты, тесты, библия, запуск, границы); если не так — причина, как нужно, переделывать до правильного. Исправлено: комментарий в employees.json (источник истины: JSON → sync_employees.py). Ссылки в HOW_TO_INDEX и §8. См. CHANGES §0.4at.

Последние изменения (2026-02-09): **Как мы мыслим: подход и логика (§0.4as).** Документ [THINKING_AND_APPROACH.md](THINKING_AND_APPROACH.md) — для «моих» (команда и агенты): принципы, пошаговая последовательность (понять → контекст → план → выполнить → проверить → зафиксировать), как принимаются решения и обрабатываются неясности. Ссылки в HOW_TO_INDEX и §8. См. CHANGES §0.4as.

Последние изменения (2026-02-09): **Как что делать: единый индекс (§0.4ar).** Документ [HOW_TO_INDEX.md](HOW_TO_INDEX.md) — для команды и агентов: тема → runbook/команда (эксперты, куратор, миграции, тесты, восстановление, RAG, деплой); решение «план = подсказка» зафиксировано в NEXT_STEPS §5. Ссылка в §8. См. CHANGES §0.4ar.

Последние изменения (2026-02-09): **Использование базы знаний (§0.4am).** Документ [KNOWLEDGE_BASE_USAGE.md](KNOWLEDGE_BASE_USAGE.md) — кто и как использует накапливаемую базу (Victoria, Veronica, оркестраторы, эксперты, Telegram); таблица точек входа. Ссылка в §8. См. CHANGES §0.4am.

Последние изменения (2026-02-09): **Архитектура подключения экспертов (§0.4al).** Документ EXPERT_CONNECTION_ARCHITECTURE.md — единый источник (employees.json) → sync → seed/БД; потребители (expert_services для промптов, БД для назначений); конфигурируемый TTL (EXPERT_SERVICES_DB_TTL); runbook добавления эксперта. Ссылки в team.md и §8. См. CHANGES §0.4al.

Последние изменения (2026-02-08): **Тестирование всей системы (§0.4aj).** Документ TESTING_FULL_SYSTEM.md — что тестировать (Victoria, Veronica, оркестраторы, эксперты), как запускать, один скрипт `./scripts/run_all_system_tests.sh` (backend 57 + knowledge_os 41 unit). Добавлены тесты: delegate_to_veronica (mock), expert_services, IntegrationBridge. См. CHANGES §0.4aj.

Последние изменения (2026-02-08): **Тесты и проверка логики цепочки (§0.4ai).** test_task_detector.py приведён к PREFER_EXPERTS_FIRST; backend/app/tests/test_task_detector_chain.py — 15 тестов (detect_task_type, should_use_enhanced, _build_orchestration_context, _orchestrator_recommends_veronica). Backend 52 теста. VICTORIA_TASK_CHAIN_FULL §9, VERIFICATION_CHECKLIST §5. См. CHANGES §0.4ai.

Последние изменения (2026-02-08): **Полная цепочка задачи Victoria (§0.4ah).** Документ VICTORIA_TASK_CHAIN_FULL.md: схема от POST /run до ответа, кто распределяет (task_detector, IntegrationBridge), кто исполняет (Veronica / Enhanced / agent_run), один эксперт или команда (swarm/consensus только для complex), разрывы и рекомендации. См. CHANGES §0.4ah.

Последние изменения (2026-02-08): **Улучшения куратора и API Victoria (§0.4ag).** Runbook: retry, ссылки INDEX и CURATOR_LIST_FILES_FAILURES; скрипт curator_compare_to_standard.py (сравнение отчёта с эталоном); POST /run — опция verbose=true, в ответе knowledge.verbose_steps (пошаговые шаги агента). NEXT_STEPS §3 обновлён. См. CHANGES §0.4ag.

Последние изменения (2026-02-08): **Причина сбоев «список файлов» в кураторе (§0.4af).** Документ docs/curator_reports/CURATOR_LIST_FILES_FAILURES.md — диагноз (connection reset при GET /run/status, возможны OOM Victoria или долгий ответ Veronica), раздел «При следующих сбоях». В кураторе: до 3 повторов GET /run/status при connection/reset; DELEGATE_VERONICA_TIMEOUT=90 по умолчанию. См. CHANGES §0.4af.

Последние изменения (2026-02-08): **Продолжение куратора (§0.4ad).** Полный прогон 5 задач, эталоны (status_project, list_files, one_line_code). Скрипт **scripts/curator_add_standard_to_knowledge.py** — добавление эталона «что ты умеешь» в knowledge_nodes (домен curator_standards); выполнен, RAG находит по ILIKE.

Последние изменения (2026-02-08): **Куратор-наставник и единый источник возможностей (§0.4ad).** Текст «что ты умеешь» — configs/victoria_capabilities.txt + configs/victoria_common.get_capabilities_text(); victoria_server и victoria_enhanced используют его. CURATOR_CHECKLIST.md и §5 VICTORIA_CURATOR_PLAN — эталоны, обучение, чеклист. NEXT_STEPS_CORPORATION.md — RAG Redis при масштабировании. См. CHANGES §0.4ad.

Последние изменения (2026-02-08): **Полный аудит корпорации и RAG-кэш (§0.4ac).** Отчёт docs/curator_reports/CORPORATION_FULL_AUDIT_2026-02-08.md: тесты, цепочки (чат→Victoria, Совет, RAG, слот), баги не найдены; в Victoria RAG-кэш — ленивое вытеснение (не более 50 устаревших за вызов). См. CHANGES §0.4ac.

Последние изменения (2026-02-08): **Подключение экспертов и решения выявленных проблем (§0.4aa).** Документ docs/PROBLEMS_AND_EXPERT_SOLUTIONS.md — сводка проблем (оркестратор 137, Ollama/MLX, тесты) с рекомендациями экспертов; исправлены ServiceMonitor.is_running(), test_load (LinkType, uuid), test_service_monitor (dict), trigger_recovery_webhook (timezone). См. CHANGES §0.4aa.

Последние изменения (2026-02-08): **«Все делаем» (§0.4y).** Проверено: backlog закрыт; asyncpg в requirements — при ошибке «asyncpg не установлен» установить зависимости (setup_knowledge_os.sh или pip install -r knowledge_os/requirements.txt); RAG+ реализован, HNSW в миграциях; остатки PROJECT_GAPS — по приоритетам. См. CHANGES §0.4y.

Последние изменения (2026-02-08): **Backlog и runbook (§0.4w).** TODO_FIXME_BACKLOG: optimize_symbol_parameters закрыт; auto_generate_tests — уточнение. Контейнер оркестратора — enhanced_orchestrator (health + webhook); ORCHESTRATOR_137_AND_OLLAMA, LIVING_ORGANISM_PREVENTION, VERIFICATION_CHECKLIST §3/§5 актуальны.

Последние изменения (2026-02-08): **Батч эмбеддингов в Victoria (§0.4v).** _get_embeddings_batch(texts); предзагрузка RAG использует один батч при поддержке API. См. RAG_PLUS_ROCKET_SPEED, CHANGES §0.4v.

Последние изменения (2026-02-08): **Предзагрузка типовых запросов в кэш RAG (§0.4u).** При старте Victoria в фоне заполняется кэш RAG запросами «статус», «список файлов» и др. RAG_PRELOAD_TYPICAL_QUERIES, RAG_CACHE_TTL_SEC>0. См. CHANGES §0.4u.

Последние изменения (2026-02-08): **Реранкинг RAG по флагу (§0.4t).** Victoria: при RAG_RERANK_ENABLED=true — limit×2 кандидатов, реранк по similarity × бонус длины, топ limit. См. RAG_PLUS_ROCKET_SPEED, CHANGES §0.4t.

Последние изменения (2026-02-08): **HNSW-проверка, Victoria /metrics, smart_worker latency, Grafana RAG, Victoria в Prometheus (§0.4s).** Скрипт verify_hnsw_index.py; Victoria GET /metrics (Prometheus); замер latency_ms в smart_worker record_attempt; дашборд victoria-rag-latency.json; job victoria-agent в prometheus/prometheus.yml и infrastructure/monitoring/prometheus.yml. См. CHANGES §0.4s.

Последние изменения (2026-02-08): **Отслеживание и проверка «тормозит» RAG+ латентности (§0.4r).** В Victoria GET /status возвращает блок **rag_latency** (last, slow_count, last_slow_at, thresholds_ms); при превышении порогов — WARNING [RAG+_latency] SLOW и увеличение slow_count. Пороги: RAG_LATENCY_EMBED_MS_MAX, RAG_LATENCY_PREPARE_MS_MAX, RAG_LATENCY_LLM_PLAN_MS_MAX. Мониторинг может опрашивать /status и строить алерты. См. RAG_PLUS_ROCKET_SPEED, CHANGES §0.4r.

Последние изменения (2026-02-08): **Метрики латентности RAG+ в Victoria (§0.4q).** В plan() замеряются embed_ms, prepare_ms (эксперт+RAG), llm_plan_ms; при RAG_LATENCY_LOG=true или VICTORIA_DEBUG=true логируются с префиксом [RAG+_latency]. См. RAG_PLUS_ROCKET_SPEED, CHANGES §0.4q.

Последние изменения (2026-02-08): **Один эмбеддинг на запрос в Victoria (§0.4p).** В точке входа (формирование промпта) эмбеддинг вычисляется один раз и передаётся в _get_knowledge_context(precomputed_embedding=...); параллель эксперт + RAG с этим эмбеддингом. См. RAG_PLUS_ROCKET_SPEED, CHANGES §0.4p.

Последние изменения (2026-02-08): **Один эмбеддинг на запрос в Victoria (§0.4p).** В точке входа (формирование промпта) эмбеддинг вычисляется один раз и передаётся в `_get_knowledge_context(goal, precomputed_embedding=...)`; параллель: эксперт + RAG с этим эмбеддингом. См. RAG_PLUS_ROCKET_SPEED, CHANGES §0.4p.

Последние изменения (2026-02-08): **Кэш контекста RAG в Victoria (§0.4o).** В `_get_knowledge_context()` добавлен in-memory кэш по ключу `md5(goal.strip().lower())`. При попадании контекст возвращается без вызова эмбеддинга и БД. TTL: `RAG_CACHE_TTL_SEC` (120 с, 0 = выкл), макс. 500 записей. См. RAG_PLUS_ROCKET_SPEED, VERIFICATION_CHECKLIST §5 (узлы знаний и RAG), CHANGES §0.4o.

Последние изменения (2026-02-08): **Предотвращение повторения «задачи не создаются, оркестратор 137» (§0.4n).** Runbook docs/LIVING_ORGANISM_PREVENTION.md — корневые причины, что сделано, что проверять. В VERIFICATION_CHECKLIST §3 добавлена причина «Задачи не создаются, обучение не идёт»; в §5 — пункт «Чтобы в будущем не повторялось». Подсказка Ollama в verify_mac_studio_self_recovery: system_auto_recovery или ollama serve. См. CHANGES §0.4n.

Последние изменения (2026-02-08): **Оркестратор 137 (OOM) и Ollama (§0.4l).** Причины: docker events — container oom → exit 137; на хосте не запущен ollama serve (11434), только ollama-mcp. Документ docs/ORCHESTRATOR_137_AND_OLLAMA.md; corporation_knowledge_system сначала импортирует semantic_cache.get_embedding (меньше памяти при старте). См. CHANGES §0.4l.

Последние изменения (2026-02-08): **Контейнеры оркестратора/Nightly Learner: контроль и перезапуск (§0.4k).** Причина «задачи не создавались, обучение не проходило»: контейнеры knowledge_nightly и knowledge_os_orchestrator упали; скрипт самовосстановления делал `restart` (не поднимает остановленные). Исправлено: при остановленных контейнерах — `up -d`; явная проверка и подъём knowledge_nightly и knowledge_os_orchestrator в system_auto_recovery.sh и check_and_start_containers.sh. См. CHANGES_FROM_OTHER_CHATS §0.4k, WHY_NO_LEARNING_DEBATES_HYPOTHESES_TASKS §0.

Последние изменения (2026-02-15): 
- **Политика портов (§0.5a):** Создан `docs/PORT_REGISTRY.md`. Порты CORE (8010, 8011, 8080, 3000) объявлены неприкосновенными.
- **Проект Сетки 21 (§0.4j):** Зарегистрирован в реестре (slug: setki-21). Настроены порты 8081 и 3003.

Последние изменения (2026-02-06): **Улучшай: RAG relevance (§0.4h).** keyword-first в evaluate_rag_quality — приоритет чанкам «Вопрос: X Ответ: Y»; seed_knowledge_from_dataset; relevance 1.0, All thresholds passed. См. CHANGES_FROM_OTHER_CHATS §0.4h.

Последние изменения (2026-02-05): **Доделывай: E2E Playwright, Ruff config, coverage baseline (§0.4g).** (1) E2E: tests/e2e/ (health, chat), frontend e2e/e2e:ui, workflow e2e-playwright.yml. (2) pyproject.toml [tool.ruff]: ignore F401,F841, exclude cache_normalizer_rs. (3) scripts/measure_coverage_baseline.sh. См. CHANGES_FROM_OTHER_CHATS §0.4g.

Последние изменения (2026-02-05): **Делайте: TODO backlog, ruff в CI, auth /metrics (§0.4f).** (1) docs/TODO_FIXME_BACKLOG.md — приоритизация TODO. (2) pytest-knowledge-os.yml — job lint (ruff). (3) VERIFICATION_CHECKLIST §5 — решение по /metrics. См. CHANGES_FROM_OTHER_CHATS §0.4f.

Последние изменения (2026-02-05): **Замечания PROJECT_GAPS: актуализация с командой (§0.4e).** §2 «CI не гоняет pytest» и §3 «Один workflow» приведены в соответствие с текущим состоянием (pytest-knowledge-os.yml на push/PR). См. CHANGES_FROM_OTHER_CHATS §0.4e.

Последние изменения (2026-02-05): **Выполнение задач по порядку (§0.4d).** (1) **Grafana:** provisioning алерта deferred_to_human > 10 (grafana/provisioning/alerting/deferred_to_human.yaml); datasource uid: prometheus. (2) **Victoria:** executor.ask(phase=…) — при таймауте лог содержит understand_goal|plan|step_N. (3) **system_auto_recovery:** проверка и перезапуск Ollama после sleep/wake (блок 4.5, здоровье, без интернета). См. CHANGES_FROM_OTHER_CHATS §0.4d.

Последние изменения (2026-02-05): **Victoria: не обрывать ответы — таймауты.** VICTORIA_TIMEOUT 900 с (15 мин); send_message обёрнут в wait_for с 504 при превышении; OLLAMA_EXECUTOR_TIMEOUT 300 с (настраиваемый). См. CHANGES_FROM_OTHER_CHATS §0.4c.

Последние изменения (2026-02-05): **Victoria: лимит 500 шагов и долгие ответы (чат, Telegram).** Для чата (localhost:3000) и Telegram снижен лимит шагов: backend передаёт **max_steps=50** (VICTORIA_MAX_STEPS_CHAT, по умолчанию 50); run_stream тоже передаёт max_steps; Telegram-бот использует **VICTORIA_MAX_STEPS** (по умолчанию 50). Сообщение при превышении лимита дополнено: «Упростите запрос или разбейте задачу на части.» См. CHANGES_FROM_OTHER_CHATS §0.4b.

Последние изменения (2026-02-05): **Выполнение оставшихся задач (PROJECT_GAPS).** (1) **Grafana:** дашборд knowledge_os-tasks.json — панели deferred_to_human_total и last_error_total; рекомендация алерта при > 10. (2) **Тесты:** board/consult без X-API-Key → 401; GET /metrics содержит knowledge_os_tasks_deferred_to_human_total; backend test_strategic_classifier (is_strategic_question, get_risk_level). (3) Порог покрытия CI оставлен 0 до замера базовой линии. См. CHANGES_FROM_OTHER_CHATS §0.4a.

Последние изменения (2026-02-05): **Методология работы (подтверждение).** Пользователь подтвердил: делать как нужно, советоваться со специалистами (.cursor/rules/, VERIFICATION_CHECKLIST, CHANGES), постоянно проверять результат и исправлять ошибки, сверяться с мировыми практиками, устранять причины возникновения, сверяться с библией и обновлять её. См. § «Как пользоваться» → «Методология работы», §6, CHANGES_FROM_OTHER_CHATS §0.3z.

Последние изменения (2026-02-05): **Фронтовые тесты (PROJECT_GAPS §2).** В frontend/ добавлены Vitest, jsdom, @testing-library/svelte; скрипты `npm run test`, `npm run test:watch`; smoke-тесты чат-стора (chat.spec.js — 4 теста). E2E (чат, health) — Playwright по возможности позже. VERIFICATION_CHECKLIST §2 и PROJECT_GAPS §2 обновлены. См. CHANGES_FROM_OTHER_CHATS §0.3y.

Последние изменения (2026-02-05): **Единый индекс планов и отчётов (PROJECT_GAPS §5).** Создан [PLANS_AND_REPORTS_INDEX.md](PLANS_AND_REPORTS_INDEX.md): планы (.cursor/plans/), архив (docs/archive/), learning_programs/, ai_insights/. Ссылка в §8. PROJECT_GAPS §5 обновлён. См. CHANGES_FROM_OTHER_CHATS §0.3x.

Последние изменения (2026-02-05): **Порог покрытия в CI (PROJECT_GAPS §2).** В workflow pytest-knowledge-os.yml добавлен **--cov-fail-under** (env COVERAGE_FAIL_UNDER, по умолчанию 0). После замера базовой линии поднять в workflow (например 5 или 10). VERIFICATION_CHECKLIST §2 и PROJECT_GAPS §2 обновлены. См. CHANGES_FROM_OTHER_CHATS §0.3w.

Последние изменения (2026-02-05): **Мониторинг deferred_to_human и last_error (PROJECT_GAPS §3).** В GET /metrics (knowledge_rest 8002) добавлены метрики **knowledge_os_tasks_deferred_to_human_total** и **knowledge_os_tasks_deferred_last_error_total**{error_type=timeout|empty_or_short_response|validation_failed|connection_error|oom_or_metal|other}. Реализация в knowledge_os/app/rest_api.py (_deferred_metrics_prometheus, _normalize_last_error_type). VERIFICATION_CHECKLIST §3 и PROJECT_GAPS §3 обновлены. Алерты в Grafana — настроить по порогу. См. CHANGES_FROM_OTHER_CHATS §0.3v.

Последние изменения (2026-02-05): **Границы src/ и knowledge_os (PROJECT_GAPS §1).** Создан документ [SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md](SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md): явно зафиксировано, какой путь продакшен для какого домена (knowledge_os/app — корпорация; src/agents/bridge — Victoria Server/Bot; src/ остальное — торговля). В MASTER_REFERENCE добавлен §1г; в VERIFICATION_CHECKLIST §5 — пункт при правках в этих зонах. PROJECT_GAPS §1 обновлён: статус «Частично (2026-02-05): задокументировано». См. CHANGES_FROM_OTHER_CHATS §0.3u.

Последние изменения (2026-02-05): **Покрытие тестами в CI (PROJECT_GAPS §2).** В workflow pytest-knowledge-os.yml добавлены pytest-cov, отчёт по knowledge_os.app (xml + term-missing) и артефакты coverage-no-db и coverage-with-db. В knowledge_os/requirements.txt — pytest-cov>=4.1.0. Порог (--cov-fail-under) можно ввести после замера базовой линии. VERIFICATION_CHECKLIST §2 и PROJECT_GAPS §2 обновлены. См. CHANGES_FROM_OTHER_CHATS §0.3t.

Последние изменения (2026-02-05): **Секреты и один воркер (по PROJECT_GAPS §4, §8).** (1) **download_from_server46.sh:** дефолтный пароль убран из репо; приоритет SSH-ключей (ssh_cmd/scp_cmd с BatchMode=yes); SERVER_46_PASS только из окружения (.env не коммитить). (2) **VERIFICATION_CHECKLIST §5:** добавлены пункты «Секреты» (не коммитить .env, шаблоны без секретов, в проде — секрет-менеджер; скрипты без дефолтного пароля, приоритет SSH-ключей) и «Деплой воркера» (проверять docker ps — один контейнер воркера на окружение). PROJECT_GAPS_ANALYSIS §4 обновлён: статус download_from_server46 — принято. См. CHANGES_FROM_OTHER_CHATS §0.3s.

Последние изменения (2026-02-05): **CI: прогон pytest Knowledge OS.** Добавлен workflow `.github/workflows/pytest-knowledge-os.yml`: (1) **pytest-no-db** — тесты `test_json_fast_http_client` (8 тестов, без БД) при push/PR в main; (2) **pytest-with-db** — Postgres (pgvector/pgvector:pg16), init schema (knowledge_os/db/init.sql), apply_migrations.py, тесты `test_rest_api`, `test_victoria_chat_and_request`. Устраняет пробел из PROJECT_GAPS_ANALYSIS: CI не гонял основной pytest-набор. См. CHANGES_FROM_OTHER_CHATS §0.3r.

Последние изменения (2026-02-05): **Детальные правила экспертов в .cursor/rules/ (по образцу rules2).** Для ядра команды (Виктория, Игорь, Роман, Дмитрий, Сергей, Анна, Елена, Максим, Татьяна) правила расширены до формата «что умеет и что знает»: **When to use**, **Positioning**, **Core principles**, **Responsibilities**, **Artifacts**, **Workflow**, примеры промптов и критерии качества. Артефакты и workflow привязаны к atra-web-ide (MASTER_REFERENCE, VERIFICATION_CHECKLIST §1/§3/§5, пути backend/, knowledge_os/, scripts/). Остальные эксперты (76+) остаются в кратком формате. См. CHANGES_FROM_OTHER_CHATS §0.3q.

Последние изменения (2026-02-05): **Анализ недостатков проекта (Виктория и команда).** Создан документ [PROJECT_GAPS_ANALYSIS_2026_02_05.md](PROJECT_GAPS_ANALYSIS_2026_02_05.md): недостатки по зонам (Backend, QA, SRE, Security, Docs, Performance), приоритеты, связь с чеклистом и §5 «При следующих изменениях». Ключевые точки: CI без основного pytest, дублирование src/ и knowledge_os/, employees.json vs БД, секреты в env, много TODO, мониторинг deferred_to_human.

Последние изменения (2026-02-05): **Число экспертов — 86, источник истины БД (Docker).** В документации и docker-compose везде заменено «85 экспертов» на **86**; источник истины — таблица `experts` в PostgreSQL (knowledge_postgres). Отчёт: `knowledge_os/scripts/reports/experts_check_report.txt`. Обновлены: MASTER_REFERENCE, CHANGES_FROM_OTHER_CHATS, VERONICA_REAL_ROLE, docker-compose.yml, .cursorrules, configs/experts/team.md (уточнено: в БД 86, в employees.json — для sync).

Последние изменения (2026-02-14): **Singularity 10.0: Unified Chat Architecture.** (1) **Victoria Agent** стал единой точкой входа для всех интерфейсов (Web IDE, Dashboard, Telegram, CLI). (2) В `victoria_server.py` добавлен эндпоинт `/stream` с поддержкой SSE, детекцией эмоций (`EmotionDetector`) и умным роутингом. (3) **Smart Routing:** простые запросы («привет», «как дела») обрабатываются мгновенно через локальные модели (MLX/Ollama) внутри Victoria, сложные задачи идут в экспертную цепочку Enhanced. (4) Бэкенд чата (`backend/app/routers/chat.py`) превращен в тонкий прокси. (5) **Resilience:** автоматический fallback между MLX, Ollama и Victoria Enhanced.

Последние изменения (2026-02-05): Интеграция Atra Core. Объединение стратегического лидерства и персонального опыта экспертов (Игорь, Роман, Дмитрий) с инфраструктурой Singularity 9.0. Внедрены стандарты UTC, идемпотентности и метод группового обсуждения экспертов. См. .cursorrules.

**Последние изменения (2026-02-04):** **MLX API: таймауты по моделям (загрузка + инференс + запас).** У каждой модели разное время загрузки и инференса; раньше использовались фиксированные 300 с. Введены: (1) **MODEL_TIME_ESTIMATES** в `knowledge_os/app/mlx_api_server.py` — для каждой модели (104b, 70b, 32b, 3b, 1b и др.) заданы load_sec, inference_sec_per_1k, margin_sec; для неизвестных — fallback по размеру из имени. (2) **get_model_timeout_estimate(model_key, max_tokens, load_time_actual)** — полный таймаут = загрузка (факт из кэша или оценка) + (max_tokens/1000 × inference_sec_per_1k) + margin. (3) Таймаут **ожидания слота** в middleware задаётся через **MLX_QUEUE_WAIT_TIMEOUT** или автоматически как максимум по всем моделям (2k токенов). (4) Таймаут **генерации** в _generate_text_internal и таймаут **очереди** (add_request, wait_for) используют эту оценку по модели и max_tokens. Health/read-only (/ , /health, /api/tags) не занимают слот. См. CHANGES_FROM_OTHER_CHATS §0.3m.

**Последние изменения (2026-02-04):** **Дашборд корпорации: рендер только по разделу (под ключ).** В Corporation Dashboard (8501) навигация по **6 разделам** в сайдбаре; при выборе раздела рендерятся **только подвкладки этого раздела** (ленивая загрузка по DASHBOARD_OPTIMIZATION_PLAN). Обзор — единая точка входа (st.stop); Задачи — 2 подвкладки (Список задач, Поставить задачу); Разведка и симуляции — 3 (Симулятор, Маркетинг, Разведка); **Стратегия и эксперты** — 5 подвкладок (Ликвидность, Структура, OKR, Решения Совета, Академия ИИ), контент вынесен в _render_liquidity, _render_structure, _render_okr, _render_board_decisions, _render_academy; Аналитика и качество / Система и агент — заглушки с подсказкой (подвкладки подключаются по плану). Блок из 23 вкладок удалён (~2400 строк); параметризованный запрос в _render_board_decisions. См. DASHBOARDS_AND_AGENTS_FULL_PICTURE §4, CHANGES_FROM_OTHER_CHATS §0.3j.

**Последние изменения (2026-02-04):** **Методология работы.** В .cursorrules добавлен раздел «Методология работы»: делать как нужно, советоваться со специалистами (роли в .cursor/rules/, VERIFICATION_CHECKLIST, CHANGES_FROM_OTHER_CHATS), постоянно проверять результат и исправлять ошибки, сверяться с мировыми практиками, устранять причины сбоев, сверяться с библией и обновлять её. В MASTER_REFERENCE добавлен подраздел «Методология работы» в § «Как пользоваться». См. CHANGES_FROM_OTHER_CHATS §0.3h.

**Последние изменения (2026-02-04):** **Порядок везде.** (1) Файлы .backup из исходников перенесены в **docs/archive/obsolete_backups/** (например src/filters/manager.py.backup). (2) В .gitignore добавлены *.backup, *.bak, *.swp, *.tmp (мировая практика: не коммитить бэкапы и временные файлы). (3) В PROJECT_ARCHITECTURE_AND_GUIDE §2 уточнена структура: корень (README, PLAN, VICTORIA, VERONICA, requirements), docs/archive (root_reports, obsolete_backups). См. docs/archive/README.md.

**Последние изменения (2026-02-04):** **Порядок в папках: архив корневых отчётов.** Одноразовые отчёты и статусы из корня репозитория перенесены в **docs/archive/root_reports/** (исторические COMPLETE_*, FINAL_*, VICTORIA_*, TELEGRAM_* и др.). В корне оставлены: README.md, PLAN.md, VICTORIA.md, VERONICA.md, requirements.txt и конфиги/скрипты. В .gitignore добавлены артефакты сборки: target/, *.o, *.rlib, *.dylib, *.a. Актуальная документация — docs/ (MASTER_REFERENCE и таблица документов §8). См. docs/archive/README.md.

**Последние изменения (2026-02-04):** **Использование normalize_and_hash_batch в embedding_optimizer.** В `get_embeddings_batch` хэши для списка текстов получаются одним вызовом `_get_text_hashes_batch(texts)` (внутри — Rust `normalize_and_hash_batch` при наличии), затем поиск по кэшу через `_get_cached_embedding_by_hash`. Один переход Python↔Rust на батч вместо N. Логика кэша (память → БД) вынесена в `_get_cached_embedding_by_hash`; `get_cached_embedding` и батч её переиспользуют. Тесты и проверка совпадения с одиночным хэшем — ок. См. CORPORATION_RUST_ROADMAP §5 (использование batch в Python).

**Последние изменения (2026-02-04):** **Корпорация на Rust: дорожная карта и batch.** (1) Документ [CORPORATION_RUST_ROADMAP.md](CORPORATION_RUST_ROADMAP.md) — стратегия поэтапного наращивания Rust (видение, принципы по чеклисту и библии, фазы, следующие шаги). (2) В cache_normalizer_rs добавлена батч-функция **normalize_and_hash_batch(texts)** — меньше переходов Python↔Rust при массовой обработке; контракт и fallback сохранены. См. CHANGES_FROM_OTHER_CHATS §0.3c.

**Последние изменения (2026-02-04):** **Rust cache_normalizer: faster-hex.** В `cache_normalizer_rs` для hex-кодирования MD5 используется крейт **faster-hex** (SIMD, быстрее `format!("{:x}")`); в батче — `Vec::with_capacity`. Контракт с Python сохранён (тесты и проверка совпадения с hashlib). См. OPTIMIZATION_AND_RUST_CANDIDATES §4.

**Последние изменения (2026-02-04):** **Ускорение Rust cache_normalizer.** В `knowledge_os/cache_normalizer_rs`: (1) нормализация без промежуточного `Vec` — один проход в `String::with_capacity`; (2) профиль release: `opt-level=3`, `lto="thin"`, `codegen-units=1`; (3) юнит-тесты в Rust (пустая строка, пробелы, консистентность хэша, MD5 пустой строки); (4) при Python 3.14 сборка: `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop --release`. Контракт с Python сохранён (normalize_text, normalize_and_hash совпадают с hashlib). Бенчмарк: 1000 вызовов ~0.001 с (Rust). См. OPTIMIZATION_AND_RUST_CANDIDATES §4, cache_normalizer_rs/README.md.

**Последние изменения (2026-02-04):** **Причина сбоя и задержка перед повтором (меньше вылетов в ручную проверку).** При пустом ответе/таймауте/исключении воркер сохраняет **last_error** в metadata (timeout, текст исключения или empty_or_short_response), передаёт его в Совет при эскалации и при завершении с deferred_to_human. В дашборде для задач «Ручная проверка» отображается **Причина сбоя** из metadata.last_error. Чтобы не бить LLM сразу после сбоя, перед повторной попыткой задаётся задержка: **next_retry_after** (env `SMART_WORKER_RETRY_DELAY_SEC`, по умолчанию 90 с); воркер выбирает pending-задачи только с `next_retry_after IS NULL OR next_retry_after < NOW()`. Так снижается число задач, попадающих в ручную проверку из‑за таймаутов под нагрузкой. См. CHANGES_FROM_OTHER_CHATS §0.3k.

**Последние изменения (2026-02-04):** **Retry и эскалация в Совет Директоров.** Все задачи выполняются с единым лимитом попыток: **MAX_ATTEMPTS=3** (env `SMART_WORKER_MAX_ATTEMPTS`). После каждой неудачи (ошибка LLM, пустой ответ, провал валидации) счётчик попыток увеличивается; задача возвращается в `pending` и снова попадает в очередь. После исчерпания 3 попыток: (1) пробуется rule_executor; (2) при неудаче — **эскалация в Совет Директоров** (`strategic_board.consult_board`, source=task_escalation); (3) задача завершается со статусом `completed`, результат содержит решение Совета (если получено) и пометку `board_escalated`, `deferred_to_human`. Неуспешная валидация результата (task_result_validator) считается попыткой и ведёт к той же эскалации при достижении MAX_ATTEMPTS. Хелпер `escalate_task_to_board` в `smart_worker_autonomous.py`. См. CHANGES_FROM_OTHER_CHATS §0.3.

**Таймаут запроса к LLM (2026-02-04):** Чтобы часть задач не уходила в ручную проверку при работающих MLX/Ollama («не дожидаемся ответа»), таймаут HTTP-запроса к узлам задаётся через **LOCAL_ROUTER_LLM_TIMEOUT** (по умолчанию **300** с) в local_router и ai_core (Ollama fallback). Воркер (SMART_WORKER_LLM_TIMEOUT=300) и роутер ждут одинаково долго. См. CHANGES_FROM_OTHER_CHATS §0.3a, VERIFICATION_CHECKLIST §3 (Часть задач не дожидается ответа).

**Прокси Claude Code → Victoria (2026-02-04):** В репозитории добавлен **proxy/** — FastAPI-сервис, принимающий запросы в формате Anthropic Messages API (`POST /v1/messages`) и переводищий их в Victoria `POST /run`. Ответ возвращается в формате Anthropic. Claude Code при `ANTHROPIC_BASE_URL=http://localhost:8040` (или 185:8040) использует экспертов и оркестраторы корпорации. Запуск: `VICTORIA_URL=http://localhost:8010 uvicorn proxy.main:app --host 0.0.0.0 --port 8040`. См. proxy/README.md, docs/CLAUDE_CODE_LOCAL_MODELS.md §4.

**Ранее (2026-02-04):** **Автоочистка старых задач.** Удаление задач `completed` старше 30 дней и всех `cancelled` выполняется автоматически: (1) **Nightly Learner** — Phase 17 в каждом цикле; (2) **Enhanced Orchestrator** — раз в сутки (ключ Redis `last_tasks_cleanup`). Ручная очистка остаётся на дашборде (кнопки «Очистить старые завершенные», «Очистить cancelled»).

**Ранее (2026-02-04):** **Дедупликация задач от обучения (Curiosity / ИССЛЕДОВАНИЕ).** Одна и та же задача (title + description) для одного эксперта не создаётся чаще одного раза за 30 дней. Хелпер `knowledge_os/app/task_dedup.py`: `same_task_for_expert_in_last_n_days(conn, title, description, assignee_expert_id, days=30)`. Интеграция: Enhanced Orchestrator Phase 5 (Curiosity) — перед INSERT проверка через `get_best_expert_for_domain` и дедупликация по эксперту; Streaming Orchestrator `_run_curiosity_engine` — проверка перед INSERT для выбранного assignee. При дубликате — skip с логом. Относится к задачам, создаваемым из обучения (curiosity_engine_starvation). См. CHANGES_FROM_OTHER_CHATS §0.2, VERIFICATION_CHECKLIST_OPTIMIZATIONS §3 (причина дубликатов), §5 (при следующих изменениях оркестратора), пункт 37 чеклиста.

**Ранее (2026-02-03):** **Эмбеддинги 768 и веб-поиск.** (1) Размерность эмбеддингов унифицирована на 768 (nomic-embed-text): миграция `fix_embedding_dimensions_768.sql`, semantic_cache (EMBEDDING_DIM, проверка перед save), дашборд/fallback и scout/tacit_knowledge_miner — везде 768. Устраняет ошибку «expected 384 dimensions, not 768» при записи в кэш. (2) Пакет `duckduckgo-search` добавлен в requirements (knowledge_os и корень) для Veronica/веб-поиска. См. CHANGES_FROM_OTHER_CHATS §0.1, CHECK_TASKS_IN_PROGRESS_20260203.

**Ранее (2026-02-03):** **Управление и мониторинг проектов с дашборда.** Добавлены: `GET /api/projects` (список проектов); вкладка дашборда «📁 Проекты»; фильтр задач по project_context; выбор проекта при создании задачи (все формы) и запись в `tasks.project_context`. §1б дополнен. См. CHANGES_FROM_OTHER_CHATS §0.

**Ранее (2026-02-03):** **Корпорация как мозг, реестр проектов.** Таблица `projects` (миграция add_projects_table.sql), загрузка реестра в Victoria/Veronica из БД с fallback на env; регистрация проекта: скрипт `scripts/register_project.py` и `POST /api/projects/register`; колонка `tasks.project_context` для изоляции; §1а, §1б, §1в в библии, NEW_PROJECT_MINIMAL_STEPS.md, .env.client.example. См. CHANGES_FROM_OTHER_CHATS §0.

**Последние изменения (2026-01-27):** **План верификации и аудит (выполнено).** По планам verification_and_architecture_plan и аудит_и_план: в PROJECT_ARCHITECTURE_AND_GUIDE добавлен §10.2 «Задачи из БД: tasks → воркер → Ollama/MLX» (поток от оркестратора до LocalAIRouter); в CURRENT_STATE_WORKER_AND_LLM §6 — явная ссылка на чеклист пункты 14–19. WORKER_THROUGHPUT уже указывает пункты 14–19; Smart Worker и ссылки на WORKER_THROUGHPUT/OLLAMA_MLX в PROJECT_ARCHITECTURE уже были. Верификация: backend/Victoria/Veronica health 200; тесты knowledge_os (json_fast, rest_api, victoria_chat_and_request) — 23 passed. См. VERIFICATION_CHECKLIST_OPTIMIZATIONS пункты 14–19, 21, 36.

**Анализ сессии (2026-01-27): что улучшили, что не ухудшили.**  
Улучшено: (1) Совет Директоров в чате — стратегические вопросы получают структурированное решение и ответ через Victoria; (2) документация — поток задач (tasks → воркер → LLM) в PROJECT_ARCHITECTURE §10.2, явные ссылки на чеклист 14–19 в CURRENT_STATE; (3) три плана закрыты (board_victoria_chat_integration, verification_and_architecture_plan, аудит_и_план). Не ухудшено: тесты knowledge_os 23 passed, линтер без ошибок по изменённым файлам (chat, strategic_classifier, strategic_board, rest_api); fallback при ошибке board/consult сохранён; контракт Victoria (goal, project_context) не менялся. Рекомендации специалистов (VERIFICATION_CHECKLIST, причины сбоев, «при следующих изменениях») учтены; библия обновлена.

**Ранее (2026-01-27):** **Совет Директоров — Victoria — Чат.** Стратегические вопросы в чате: классификатор (strategic_classifier) → вызов Knowledge OS `POST /api/board/consult` → решение Совета сохраняется в `board_decisions` (session_id, user_id, source=chat) → промпт с блоком [РЕШЕНИЕ СОВЕТА ДИРЕКТОРОВ] передаётся в Victoria → ответ пользователю. Реализовано для SSE (stream) и для POST /api/chat/send. Дашборд (8501): вкладка «Решения Совета» — фильтры по источнику, риску, correlation_id. Миграция: `knowledge_os/db/migrations/add_board_decisions.sql`. При ошибке board/consult чат продолжает работу с Victoria без решения (fallback). См. CHANGES_FROM_OTHER_CHATS §11.

**Ранее (2026-02-03):** **Phase 16 Nightly Learner.** При merge в main за 24ч создаётся задача «Синхронизировать документацию» для Technical Writer (assignee_hint). Living Organism §8, правило библии.

**Ранее:** Phase 15 авто-профилирование. Планы обновлены.

**Ранее (2026-02-03):** **Retention traces + статус Living Organism.** cleanup_old_traces в CORPORATION_PLANNING_CALENDAR; §5а «Living Organism / Living Brain: статус планов» — таблица реализованных пунктов и планы.

**Ранее (2026-02-03):** **correlation_id во всех точках входа Victoria.** Terminal /ask и Editor /autocomplete передают correlation_id в VictoriaClient.run(). Полная трассировка: чат, терминал, редактор → Victoria.

**Ранее (2026-02-03):** **correlation_id по цепочке чат → Victoria.** Backend генерирует correlation_id при каждом запросе; VictoriaClient передаёт в X-Correlation-ID; Victoria сервер использует его в логах и ответах. SSE: первый step содержит correlation_id для отладки. ARCHITECTURE_IMPROVEMENTS_ANALYSIS §1.3.

**Ранее (2026-02-03):** **Phase 14 Nightly Learner: git diff → задачи на генерацию тестов.** Анализ git log за 24ч; изменённые knowledge_os .py без тестов → задача «Сгенерировать pytest для модуля X» (assignee_hint: QA). Лимит 3 задачи за цикл. Living Brain §6.1.

**Ранее (2026-02-03):** **Робастность декомпозиции и чеклист.** Phase 1.5: при отсутствии parent_task_id в схеме — skip (try/except), лог «Phase 1.5 skipped». VERIFICATION_CHECKLIST: п.27 Tacit Knowledge, п.28 декомпозиция; причины сбоев: Tacit Knowledge, parent_task_id.

**Ранее (2026-02-03):** **Tacit Knowledge в ai_core: баг и усиление.** (1) Исправлен баг: is_coding_task использовался до определения → Tacit Knowledge никогда не срабатывал. is_coding_task перенесён выше блока Tacit Knowledge. (2) Расширены keywords для распознавания coding-задач: напиши, создай, реализуй, добавь, исправь, функци, класс, модуль, api, endpoint. (3) ROLE_PROMPT_TEMPLATES: добавлен шаблон для Prompt Engineer (Арина).

**Ранее (2026-02-03):** **Code-Smell Predictor: верификация интеграции.** code_auditor использует CodeSmellPredictor при создании задач; enhanced_orchestrator даёт приоритет задачам с source=code_auditor (severity=high → +40). Smart Worker обрабатывает их как обычные задачи. Интеграция подтверждена.

**Ранее (2026-02-03):** **Декомпозиция сложных задач из БД (Phase 1.5).** Enhanced Orchestrator: для задач priority=high/urgent или metadata.complex=true вызывает Victoria для разложения на подзадачи; создаёт записи в tasks с parent_task_id; назначает каждую подзадачу эксперту; помечает оригинал metadata.decomposed=true. Лимит 3 задачи за цикл, max 5 подзадач. См. ORCHESTRATION_IMPROVEMENTS §3.2.

**Ранее (2026-02-03):** **Backend: session_id и chat_history в VictoriaClient.** VictoriaClient.run() и run_stream() принимают session_id, chat_history; payload для Victoria POST /run включает их. Chat router (SSE и /send) передаёт session_id и chat_history_vic (из conversation_context). ConversationContextManager.to_victoria_chat_history() конвертирует формат.

**Ранее (2026-02-03):** **Фаза автотестов в Nightly Learner (Phase 13).** Запуск pytest (test_json_fast_http_client, test_rest_api); результат в knowledge_nodes; при провале — задача для QA. См. CORPORATION_PLANNING_CALENDAR.

**Ранее (2026-02-03):** **Session context в Victoria при session_id.** При вызове Victoria API с session_id без chat_history — victoria_server вызывает session_context_manager.get_session_context и подмешивает в context["chat_history"]. Работает для прямых вызовов (скрипты, Telegram). Backend уже передаёт контекст в goal через context_prefix.

**Ранее (2026-02-03):** **Ретривал по успешным решениям в ai_core.** В _get_knowledge_context добавлен третий параллельный запрос: выборка из knowledge_nodes где source_ref='autonomous_worker', confidence_score>=0.8, по similarity к запросу (limit 2). Форматируется как [ПРИМЕР УСПЕШНОГО РЕШЕНИЯ] в контекст — похожие цели получают примеры в промпт.

**Ранее (2026-02-03):** **ReActAgent: рефлексия при ошибках, интеграция request_approval.** (1) При observation с Error/ошибка/требуется одобрение — промпт рефлексии явно просит проанализировать причину и предложить другой подход. (2) Перед create_file/write_file при блокировке approval_manager вызывается get_hitl().request_approval() — создаётся запрос с request_id для будущего UI; агент получает сообщение с request_id.

**Ранее (2026-02-03):** **Victoria task_plan_struct: улучшенный парсинг JSON.** В _think_and_create_prompt_for_veronica добавлен _try_parse_llm_json: несколько попыток (trailing comma, markdown fences), меньше падений при «почти-валидном» JSON от LLM → чаще task_plan_struct без повторного вызова Victoria. Исправлен баг: при prompt_data=None цикл по subtasks вызывал AttributeError — используется (prompt_data or {}).get.

**Ранее (2026-02-03):** **Живой мозг: Prompt Engineer, Self-Check→задачи, календарь, библия.** (1) Добавлена роль Prompt Engineer (Арина) в employees.json; Knowledge Applicator создаёт задачи с assignee_hint «Prompt Engineer». (2) Self-Check при DEGRADED/UNHEALTHY без auto_fix создаёт задачу в БД (assignee_hint: SRE). (3) Создан CORPORATION_PLANNING_CALENDAR.md — единый обзор автономных циклов. (4) Уточнено: проверка после выполнения в цепочке БД уже реализована (task_result_validator в Smart Worker). См. CHANGES_FROM_OTHER_CHATS §10.

**Ранее (2026-02-03):** **Инструменты агента и HITL.** Добавлен §3а: различие Base vs Enhanced по инструментам (write_file только в ReAct); approval_manager (блокировка) vs request_approval (HITL не в основном агенте); приоритеты доработок для полноценного агента.

**Ранее (2026-02-03):** **Правило «библия при любых изменениях».** Добавлено в .cursorrules и §6 этого документа: (1) до правок — изучать библию; (2) после правок — фиксировать изменения здесь и в связанных доках. Библия всегда актуальна.

**Ранее (2026-02-03):** **Узлы знаний и RAG (польза от знаний).** В БД хранится полный content; раньше в контекст Victoria передавались только первые 200 символов на узел («частички»). Введено: RAG_SNIPPET_CHARS (500 по умолчанию), RAG_TOP1_FULL_MAX_CHARS (2000) — для топ-1 по similarity в контекст передаётся полный фрагмент до лимита (мировая практика: один полный чанк улучшает ответ). Fallback ILIKE без зависимости от usage_count: ORDER BY confidence_score DESC NULLS LAST, created_at DESC. При записи в knowledge_nodes по возможности сохранять embedding (smart_worker уже пишет embedding для отчётов). Чеклист: [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §3 (RAG частички, embedding), §5 (узлы знаний).

**Ранее (2026-02-03):** **MLX API: устойчивость и мониторинг.** (1) **Metal OOM** — процесс MLX падает при нехватке GPU-памяти (`[METAL] Insufficient Memory`, «Python завершила работу»). Решение: MLX_MAX_CONCURRENT=1 по умолчанию в start_mlx_api_server.sh; при повторных крашах — мониторинг перезапускает. (2) **InvalidStateError при таймауте:** в mlx_api_server перед set_result/set_exception проверка `if not result_future.done()` — иначе при отмене wait_for падало. (3) **Мониторинг MLX:** scripts/monitor_mlx_api_server.sh проверяет процесс и GET :11435/health каждые 30 с; при падении — перезапуск (лимит 5/час). Настройка один раз: `bash scripts/setup_system_auto_recovery.sh` — создаёт com.atra.mlx-monitor в launchd. Чеклист причин и решений: [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §3 (Metal OOM, InvalidStateError), §5 (MLX).

**Ранее (2026-02-03):** Гипотезы → дебаты: при создании кросс-доменной гипотезы (Cross-Domain Linker в Enhanced/Streaming/plain Orchestrator) или гипотезы Expert Council вызывается `create_debate_for_hypothesis()` → `run_expert_council()` → INSERT в `expert_discussions`. Debate Processor (в Nightly Learner) обрабатывает дебаты и при consensus_score ≥ 0.5 создаёт задачи. См. [HYPOTHESES_SYSTEM_STATUS.md](mac-studio/HYPOTHESES_SYSTEM_STATUS.md).

**Ранее (2026-02-03):** Ollama: запуск от правильного пользователя — модели в `~/.ollama/` (per-user). Если `brew services start ollama` стартует от nik, а модели у bikos — сервер возвращает `models: []`, 404. Решение: `brew services stop ollama`, затем `ollama serve` из терминала под bikos. Добавлена причина сбоя в VERIFICATION_CHECKLIST_OPTIMIZATIONS.md, раздел 3. Docker — независимость от atra: Redis контейнер **knowledge_os_redis**, порт хоста **6381** (6380 — atra). Удалены сироты knowledge_dashboard, knowledge_os_api (роли у corporation-dashboard и knowledge_rest). В чеклисте добавлены причины сбоев (конфликт Redis/порт) и пункт «При следующих изменениях» про Docker/Redis. Порт 6381 зафиксирован в seed_validation_answers, query_expansion, архитектуре. Воркер: убрана установка asyncpg в рантайме (12-Factor); при отсутствии зависимостей — сообщение и setup-скрипт. Адаптивный параллелизм воркера: SMART_WORKER_ADAPTIVE_CONCURRENCY=true в compose — effective_N по CPU/RAM и MLX/Ollama (потолок SMART_WORKER_MAX_CONCURRENT=15). Подробно: [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md), [CHANGES_FROM_OTHER_CHATS.md](CHANGES_FROM_OTHER_CHATS.md) §9.1, [PROJECT_ARCHITECTURE_AND_GUIDE.md](PROJECT_ARCHITECTURE_AND_GUIDE.md).

---

## Как пользоваться

- **Вопрос «как устроено?»** — разделы ниже + ссылки на детальные доки.
- **Вопрос «где описание X?»** — таблица документов в конце + поиск по ключевым словам.
- **Сделали новое или изменили подход** — добавить/обновить раздел в этом файле и при необходимости в связанном доке (WORKER_THROUGHPUT, ARCHITECTURE_FULL, CURRENT_STATE_WORKER_AND_LLM и т.д.).

### Методология работы (согласовано с .cursorrules)

При любых изменениях: (1) **делать как нужно** по постановке; (2) **советоваться со специалистами** — роли в `.cursor/rules/`, рекомендации в VERIFICATION_CHECKLIST_OPTIMIZATIONS, CHANGES_FROM_OTHER_CHATS; (3) **постоянно проверять результат** — тесты, сценарии, исправлять выявленные ошибки; (4) **сверяться с мировыми практиками** (12-Factor, backpressure, adaptive concurrency и т.д.); (5) **устранять причины сбоев**, а не только следствия, учитывать §5 чеклиста «При следующих изменениях»; (6) **сверяться с библией и обновлять её** — до правок читать MASTER_REFERENCE и связанные разделы, после — дополнять этот документ и при необходимости CHANGES_FROM_OTHER_CHATS и др.

---

## 1. Проект и архитектура (кратко)

| Что | Где подробно |
|-----|---------------|
| Структура, порты, запуск, API, метрики | [PROJECT_ARCHITECTURE_AND_GUIDE.md](PROJECT_ARCHITECTURE_AND_GUIDE.md) |
| Схема Victoria → оркестратор → эксперты → Smart Worker → Ollama/MLX | [ARCHITECTURE_FULL.md](ARCHITECTURE_FULL.md) |
| Процесс Victoria от запроса до ответа | [VICTORIA_PROCESS_FULL.md](VICTORIA_PROCESS_FULL.md) |
| Кто выполняет задачу, кто кому докладывает | [ARCHITECTURE_FULL.md](ARCHITECTURE_FULL.md), [VERONICA_REAL_ROLE.md](VERONICA_REAL_ROLE.md) |

- **Проект:** ATRA Web IDE — браузерная оболочка для ИИ-корпорации Singularity 14.0 (чат, редактор, файлы, превью).
- **Цель архитектуры:** современный автономный агент с «супер-командой» — всё необходимое для автономии в одном контуре: Victoria (Team Lead, три уровня) + 86 экспертов в БД (источник истины: таблица experts в PostgreSQL, Docker) + Совет Директоров (стратегические решения) + Veronica (исполнение шагов) + Enhanced Orchestrator + Smart Worker (задачи из БД → Ollama/MLX) + дашборды (задачи, эксперты, Решения Совета, качество). Чат, задачи, стратегия и исполнение согласованы через единую БД и API.
- **Контекст:** MAIN_PROJECT=atra-web-ide; агенты Victoria и Veronica общие для всех проектов; контекст передаётся через `project_context` в запросах.

### 1а. Реестр проектов (таблица projects)

- **Назначение:** единый источник истины для разрешённых проектов и их конфигурации (мультитенантность). Victoria и Veronica загружают список и конфиг из БД; новый проект подключается после регистрации в реестре без правок кода корпорации.
- **Схема (миграция `knowledge_os/db/migrations/add_projects_table.sql`):** таблица `projects`: `id` (UUID), `slug` (VARCHAR, UNIQUE) — идентификатор в запросах (`project_context`), `name`, `description`, `workspace_path`, `is_active` (BOOLEAN, default true), `created_at`, `updated_at`. Сидер: записи для `atra-web-ide` и `atra`.
- **Применение миграции:** при старте Knowledge OS REST API (`_ensure_projects_table_migration`) или при запуске Enhanced Orchestrator (Phase 0.5, общий прогон миграций из `db/migrations/`).

### 1б. Корпорация как мозг для всех проектов

- **Модель:** корпорация (Victoria, Veronica, оркестратор, эксперты в БД, знания) — единый общий слой («мозг»). Все проекты работают в своих зонах: различие только по `project_context` в запросах и в данных (таблица `tasks.project_context`). Проекты не влияют на код и инфраструктуру корпорации; корпорация только участвует в их работе через API.
- **Изоляция:** в каждом запросе к Victoria/Veronica передаётся `project_context`; валидация по реестру (таблица `projects`, is_active=true). В БД задачи могут быть помечены `project_context` для фильтрации в дашбордах и отчётах.
- **Управление и мониторинг с дашборда:** в дашборде корпорации (Knowledge OS dashboard): вкладка «📁 Проекты» — список зарегистрированных проектов; во вкладке «🛠️ Задачи» — фильтр по проекту и отображение project_context в карточках; при создании задачи (Симулятор, Маркетинг, Разведка, Поставить задачу) — необязательный выбор проекта, значение пишется в `tasks.project_context`. API списка проектов: `GET /api/projects` (Knowledge OS REST API, порт 8002).

### 1в. Подключение нового проекта

1. **Зарегистрировать проект в реестре** — один раз:
   - Скрипт: `python scripts/register_project.py <slug> "<name>" [--description "…"] [--workspace-path /path]` (из корня репо; требуется `DATABASE_URL`).
   - Или API: `POST /api/projects/register` (Knowledge OS REST API, порт 8002), заголовок `X-API-Key`, тело: `{"slug": "...", "name": "...", "description": "...", "workspace_path": "..."}`.
2. **В репо нового проекта:** в `.env` задать `VICTORIA_URL`, `KNOWLEDGE_OS_API_URL` (при необходимости), `PROJECT_CONTEXT=<slug>`. В запросах к backend/Victoria передавать `project_context` (тело или заголовок по контракту).
3. **Опционально:** скопировать `.cursorrules` для подсказок Cursor (см. [knowledge_os/docs/STEP_BY_STEP_NEW_PROJECT_SETUP.md](knowledge_os/docs/STEP_BY_STEP_NEW_PROJECT_SETUP.md)).
4. После регистрации агенты, оркестратор, эксперты и знания доступны проекту без дальнейших правок в корпорации. При варианте загрузки реестра при старте Victoria/Veronica — перезапуск агентов подхватывает новый проект; при TTL-кэше — подхват без рестарта.

Краткий чеклист: [NEW_PROJECT_MINIMAL_STEPS.md](NEW_PROJECT_MINIMAL_STEPS.md). Шаблон .env для проекта-клиента: [.env.client.example](../.env.client.example).

### 1г. Границы src/ и knowledge_os (дублирование кода)

- **Назначение:** явно зафиксировать, какой путь — продакшен для какого домена, чтобы при правках не допускать расхождения логики (рекомендация PROJECT_GAPS_ANALYSIS §1).
- **knowledge_os/app/** — корпорация: оркестратор, REST API, Smart Worker, эксперты, знания, дашборды. Единый источник истины для чата/задач/агентов Web IDE. Backend вызывает Knowledge OS API и Victoria.
- **src/agents/bridge/** — Victoria Server (POST /run) и Victoria Telegram Bot. Запускаются из knowledge_os/docker-compose (victoria-agent). Точка входа Victoria (8010).
- **src/** (остальное: telegram как торговый бот, signals, execution, filters, config, data, utils) — домен алгоритмической торговли; для Web IDE не используется. При правках учитывать возможное расхождение при наличии аналогов в knowledge_os.
- **Подробно:** [SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md](SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md). При изменениях в этих зонах — сверять с чеклистом §5 и при необходимости обновлять границы в том документе.

---

## 2. Компоненты и порты (сводка)

| Компонент | Порт | Описание |
|-----------|------|----------|
| Frontend | 3000 → 3002 | Svelte, чат, редактор. В docker-compose Web IDE проброшен на 3002. |
| Backend | 8080 | FastAPI: чат/stream, plan, RAG, метрики, A/B. Семафор на Victoria. |
| Victoria | 8010 | Team Lead, один сервис, три уровня (Agent, Enhanced, Initiative). |
| Veronica | 8011 | Local Developer, вызывается только Victoria. |
| PostgreSQL | 5432 | knowledge_postgres, БД knowledge_os. |
| Redis | 6379 (в сети), 6381 (хост) | knowledge_os_redis из Knowledge OS (atra — отдельный проект). |
| Prometheus Web IDE | 9091 | Метрики backend. |
| Grafana Web IDE | 3002 | Дашборды чата/бэкенда. |
| Prometheus Knowledge OS | 9092 | Метрики Knowledge OS. |
| Grafana Knowledge OS | 3001 | Дашборды оркестрации, БЗ, агентов. |
| Smart Worker | — | Обработка задач из БД (pending → in_progress → completed). |
| Ollama | 11434 | LLM на хосте. |
| MLX API | 11435 | LLM на хосте. |
| Corporation Dashboard | 8501 | Streamlit, задачи, эксперты, разведка, симуляции, **Решения Совета**. |
| Knowledge REST API | 8002 | knowledge_rest: логирование чата, **POST /api/board/consult** (консультация Совета). |

Полная картина дашбордов и агентов: [DASHBOARDS_AND_AGENTS_FULL_PICTURE.md](DASHBOARDS_AND_AGENTS_FULL_PICTURE.md).

---

## 3. Логика: чат и задачи

- **Чат:** Пользователь → Frontend (3002) или API → Backend (8080) → Victoria (8010) POST /run. Ответ SSE или 202 + task_id. **Стратегические вопросы:** перед вызовом Victoria backend вызывает классификатор `is_strategic_question()`; при True — запрос в Knowledge OS `POST /api/board/consult` (source=chat, session_id, user_id, correlation_id); решение Совета пишется в `board_decisions` и передаётся в промпт Victoria блоком [РЕШЕНИЕ СОВЕТА ДИРЕКТОРОВ]. При недоступности board/consult чат идёт в Victoria без решения (fallback).
- **Задачи в БД:** Два входа — (1) пользователь/API/дашборд создаёт task с assignee_expert_id=NULL; (2) Enhanced Orchestrator назначает эксперта. Smart Worker берёт pending по assignee_expert_id, переводит в in_progress, heartbeat каждые 15 сек, вызывает ai_core.run_smart_agent_async; по завершении — **task_result_validator** проверяет результат; при провале (score < 0.5) задача возвращается в pending; при успехе — completed. Зависшие (updated_at старше SMART_WORKER_STUCK_MINUTES) сбрасываются в pending.
- **Делегирование:** Victoria отправляет в Veronica только простые шаги или одно действие; целые задачи решают Victoria + эксперты из БД (86; счёт из Docker/PostgreSQL). PREFER_EXPERTS_FIRST=true: (1) task_detector — «сделай/напиши код» → enhanced; (2) victoria_enhanced._should_delegate_task — в Veronica только простые одношаговые (_is_simple_veronica_request). Верификация: пункт 20 чеклиста, тесты TestPreferExpertsFirstDelegation.
- **Гипотезы → дебаты:** При создании гипотезы (Cross-Domain Linker, Expert Council) вызывается `create_debate_for_hypothesis()` → `run_expert_council()` → INSERT в `expert_discussions`. Nightly Learner вызывает Debate Processor, который при consensus_score ≥ 0.5 создаёт задачи. Знания из завершённых задач пишутся в `knowledge_nodes` с embedding для RAG.
- **Узлы знаний (knowledge_nodes) и RAG:** В БД хранится **полный** content (отчёты, инсайты). Поиск: векторный (по embedding) и текстовый (ILIKE). В контекст Victoria передаётся сниппет на узел (RAG_SNIPPET_CHARS, по умолчанию 500) и для **топ-1** по similarity — полный контент до RAG_TOP1_FULL_MAX_CHARS (2000). Эмбеддинги есть только у части узлов — семантический поиск работает по ним; остальные участвуют в ILIKE. При добавлении записей в knowledge_nodes по возможности сохранять embedding. **Размерность эмбеддингов:** везде **768** (nomic-embed-text); таблицы semantic_ai_cache, embedding_cache, knowledge_nodes — vector(768). Миграция `fix_embedding_dimensions_768.sql` при необходимости приводит колонки к 768. Дашборд/списки: в SELECT использовать LEFT(content, N). См. [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §3, §5.

Детали: [ARCHITECTURE_FULL.md](ARCHITECTURE_FULL.md), [CHAT_ORCHESTRATOR_FLOW.md](CHAT_ORCHESTRATOR_FLOW.md), [CURRENT_STATE_WORKER_AND_LLM.md](CURRENT_STATE_WORKER_AND_LLM.md), [HYPOTHESES_SYSTEM_STATUS.md](mac-studio/HYPOTHESES_SYSTEM_STATUS.md).

### 3а. Инструменты агента и Human-in-the-Loop

**Инструменты по путям выполнения:**
- **Victoria Base / Executor** (`src/agents/core/executor.py`, victoria_server): только `read_file`, `list_directory`, `run_terminal_cmd`, `ssh_run`, `finish` — **write_file отсутствует**
- **Victoria Enhanced + ReAct** (`knowledge_os/app/react_agent.py`): полный набор, включая `create_file`, `write_file`, `search_knowledge`

**Подтверждение критичных действий:**
- **approval_manager** — при `AGENT_APPROVAL_REQUIRED=true` блокирует запись в критичные файлы (package.json, .env, Dockerfile). Возвращает агенту ошибку. Интегрирован в ReActAgent.
- **human_in_the_loop.request_approval** — полноценный HITL (ожидание ответа пользователя). Реализован в `human_in_the_loop.py`, используется только в AdaptiveAgent; **не интегрирован в ReActAgent / основной агентский цикл**

**Приоритеты доработок для «полноценного» агента:** (1) Интеграция `request_approval` в ReActAgent перед `create_file`/`write_file` для критичных действий; (2) Добавить `write_file` в Victoria Base при необходимости; (3) Рефлексия и перепланирование при повторяющихся ошибках; (4) Песочница/ограничения для `run_terminal_cmd`. Подробно: планы Living Organism, Living Brain в .cursor/plans.

### 3б. Совет Директоров и чат (2026-01-27)

- **Назначение:** по стратегическим вопросам (архитектура, приоритеты, рефакторинг, сроки, качество vs скорость и т.д.) чат консультируется с «Советом Директоров» (LLM по контексту OKR/задач/знаний), получает структурированное решение и передаёт его Victoria для формулировки ответа пользователю.
- **Поток:** (1) Классификатор `backend/app/services/strategic_classifier.py` — `is_strategic_question(content)` (эвристика по ключевым словам); (2) при True backend вызывает Knowledge OS `POST /api/board/consult` (тело: question, session_id, user_id, correlation_id, source=chat); (3) `knowledge_os/app/strategic_board.py` — `consult_board()` собирает контекст (OKR, tasks, последняя директива), вызывает LLM (ai_core.run_smart_agent_async), парсит структуру (decision, rationale, risks, confidence, recommend_human_review), пишет в таблицу `board_decisions` (миграция `add_board_decisions.sql`); (4) ответ API (directive_text, structured_decision, risk_level, recommend_human_review) подставляется в промпт Victoria блоком [РЕШЕНИЕ СОВЕТА ДИРЕКТОРОВ]; (5) Victoria формулирует ответ пользователю; при recommend_human_review в ответ добавляется предупреждение.
- **Устойчивость:** при ошибке или таймауте board/consult чат продолжает с обычным вызовом Victoria (без блока решения). API board/consult защищён X-API-Key (тот же API_KEY, что для log_interaction).
- **Дашборд:** Corporation Dashboard (8501), вкладка «Решения Совета» — список записей из `board_decisions` с фильтрами по источнику (chat/api/nightly/dashboard), уровню риска, correlation_id (отладка). Полный текст директивы и structured_decision в раскрывающихся блоках.
- **Полное заседание Совета:** `run_board_meeting()` (nightly или вручную) — полный контекст за 24ч, директива пишется в `board_decisions` (source=nightly), `knowledge_nodes` (type=board_directive), `expert_discussions`.

---

## 4. Воркер и LLM (текущее состояние)

### 4.1. Сосуществование тяжелых моделей (80B) и MLX
**Критическое ограничение:** Использование тяжелых моделей в Ollama (например, `qwen3-coder-next:latest` 80B, ~52GB) блокирует значительную часть GPU-памяти (Metal). 
- **Проблема:** MLX API Server падает с ошибкой `Insufficient Memory (Metal OOM)`, если Ollama удерживала тяжелую модель.
- **Решение:** `OLLAMA_KEEP_ALIVE` в `docker-compose.yml` установлен в **300** (5 минут). Это гарантирует автоматическую выгрузку тяжелых моделей и освобождение памяти для MLX.
- **Рекомендация:** При работе с 80B моделями вручную выгружайте их после завершения задачи (`ollama stop <model>`), если требуется немедленный возврат к работе с Victoria/MLX.

### 4.2. Распределение задач

### 4.3. Порты и URL
- Victoria: `8010` (внешний), `8000` (внутренний)
- Veronica: `8011` (внешний), `8000` (внутренний)
- Ollama: `11434`
- MLX API: `11435`
- PostgreSQL: `5432`
- Redis: `6381` (хост), `6379` (внутри)

---

## 5. Автоматика и восстановление

- **system_auto_recovery.sh** (launchd, каждые 5 мин): Wi‑Fi, интернет, Docker, atra-network, Knowledge OS docker-compose up -d, Web IDE docker-compose up -d, MLX (11435), Ollama (11434), проверка Victoria (:8010/status), Veronica (:8011), сводка.
- **Мониторинг MLX API Server (мировые практики: health check + автоперезапуск):** `scripts/monitor_mlx_api_server.sh` — проверка процесса и GET :11435/health каждые 30 с; при падении процесса (Metal OOM, краш) или недоступности health — перезапуск через start_mlx_api_server.sh (лимит 5 перезапусков/час). Используется /health (легче /api/tags); / , /health, /api/tags не занимают слот генерации — отвечают сразу. **Таймауты по моделям:** загрузка + инференс (сек/1k токенов) + запас заданы в MODEL_TIME_ESTIMATES; таймаут ожидания слота — MLX_QUEUE_WAIT_TIMEOUT или макс по моделям; генерация и очередь используют get_model_timeout_estimate. Настраивается через `bash scripts/setup_system_auto_recovery.sh` — создаётся launchd-агент com.atra.mlx-monitor. Логи: ~/Library/Logs/atra-mlx-monitor.log. Причины падений MLX и решения: [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §3 (Metal OOM, InvalidStateError). См. CHANGES §0.3m.
- **check_and_start_containers.sh:** ручная проверка и запуск контейнеров; при выключенных Enhanced/Initiative — перезапуск victoria-agent.
- **Календарь автономных циклов:** [CORPORATION_PLANNING_CALENDAR.md](CORPORATION_PLANNING_CALENDAR.md) — что когда запускается, куда пишет результат.
- Настройка автозапуска и мониторинга: `bash scripts/setup_system_auto_recovery.sh` (один раз после клонирования или смены машины).
- **Retention environmental_traces:** `knowledge_os/scripts/cleanup_old_traces.py` — удаление следов старше TRACES_RETENTION_DAYS (90). Cron: раз в сутки. См. CORPORATION_PLANNING_CALENDAR.

### 5а. Living Organism / Living Brain: статус планов (2026-02-03)

| План | Реализовано | Где |
|------|-------------|-----|
| Библия, инструменты, HITL | ✅ | §3а, .cursorrules |
| Prompt Engineer (Арина) | ✅ | employees.json, ROLE_PROMPT_TEMPLATES |
| Self-Check → задачи | ✅ | self_check_system._create_recovery_task |
| CORPORATION_PLANNING_CALENDAR | ✅ | docs/CORPORATION_PLANNING_CALENDAR.md |
| Victoria task_plan_struct | ✅ | victoria_enhanced._try_parse_llm_json |
| Декомпозиция сложных задач | ✅ | enhanced_orchestrator Phase 1.5 |
| Рефлексия + request_approval | ✅ | react_agent |
| Ретривал успешных решений | ✅ | ai_core._get_knowledge_context |
| session_context в Victoria | ✅ | victoria_server, VictoriaClient |
| Автотесты (Phase 13) | ✅ | nightly_learner |
| Test Generation (Phase 14) | ✅ | nightly_learner, git diff |
| correlation_id везде | ✅ | chat, terminal, editor → Victoria |
| Tacit Knowledge баг-фикс | ✅ | ai_core is_coding_task |
| Code-Smell, ROLE_PROMPT | ✅ | sync_employees, code_auditor |
| AUTO_PROFILING_GUIDE | ✅ | docs/AUTO_PROFILING_GUIDE.md |
| Retention traces | ✅ | cleanup_old_traces.py, CORPORATION_PLANNING_CALENDAR |

| Phase 15 авто-профилирование | ✅ | nightly_learner (воскресенье), cProfile → knowledge_nodes |
| Dashboard auto-apply (safe) | ✅ | dashboard_daily_improver, AUTO_APPLY_DASHBOARD=true, max_entries патч |
| Predictive Monitor | ✅ | predictive_monitor.py, внутри Self-Check; тренды stuck/pending → задачи |
| SSE progress events | ✅ | backend chat: type=progress { step, total, status } |
| Батчинг мелких задач | ✅ | enhanced_orchestrator Phase 1.6, BATCH_SMALL_TASKS_ENABLED, batch_group в metadata |
| Smart Worker batch LLM | ✅ | SMART_WORKER_BATCH_GROUP_LLM=true, один вызов LLM на batch_group (2–3 задачи) |
| Doc sync task (Phase 16) | ✅ | nightly_learner: при merge в main за 24ч → задача для Technical Writer |

**В планах:** (пусто — все пункты Living Brain/Organism выполнены)

**Завершение планов (2026-02-03):** Living Brain и Living Organism — все todos completed. Верификация: 23 теста passed, контейнеры (orchestrator, worker, victoria, nightly и др.) работают. Батчинг включён в docker-compose.

---

## 6. Разработка и изменения

- **Правило «библия при любых изменениях»:** При любом изменении в проекте (архитектура, компоненты, API, порты, конфигурация, новые фичи): **(1) до правок** — изучить MASTER_REFERENCE и связанные доки; **(2) после правок** — обновить MASTER_REFERENCE (соответствующий раздел) и при необходимости CHANGES_FROM_OTHER_CHATS, ARCHITECTURE_FULL и др. Библия всегда актуальна.
- **Правило:** при добавлении фичи или смене подхода — обновить этот документ (соответствующий раздел) и при необходимости детальный док (ARCHITECTURE_FULL, WORKER_THROUGHPUT, CURRENT_STATE_WORKER_AND_LLM и т.д.).
- **Советоваться с специалистами:** рекомендации Backend (Игорь), QA (Анна), SRE (Елена), Performance (Ольга) закреплены в [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md). **Как применять:** в начале чеклиста — таблица «Когда / Что делать / Где смотреть»: перед правками — §5 «При следующих изменениях» по затронутому компоненту; при сбое — §3 «Причины сбоев» (найти по симптому, исправить по решению, при необходимости дополнить таблицу); после правок — §1 «Что проверять» по пунктам (воркер/Ollama/MLX: 14–19, чат: 21, Совет Директоров: 36) и тесты из §2. **Исправлять причины возникновения**, а не только симптом — тогда в будущем всё работает как нужно.
- **Постоянная проверка результата:** в процессе работы — верифицировать результат (тесты §2, пункты §1 чеклиста, логи), выявленные ошибки исправлять сразу и при необходимости дополнять §3 «Причины сбоев» и §5 «При следующих изменениях», чтобы в будущем не повторялось.
- **Мировые практики:** раздел 4 того же чеклиста (пулы, shutdown, resilience, run_in_executor, heartbeat + таймаут). При доработках сверяться с ними.
- **Решения по Rust:** при добавлении или изменении Rust-модулей сверяться с [CORPORATION_RUST_ROADMAP.md](CORPORATION_RUST_ROADMAP.md) (принципы, фазы) и §5 чеклиста (cache_normalizer_rs, стратегия «корпорация на Rust»).
- **Зависимости:** только из requirements.txt; без subprocess pip install в рантайме. При отсутствии пакета — одно чёткое сообщение с инструкцией установки.
- **Cursor:** роли в .cursor/rules/; команда экспертов в configs/experts/team.md и employees.json; индекс в .cursor/README.md. Для ядра команды (Виктория, Игорь, Роман, Дмитрий, Сергей, Анна, Елена, Максим, Татьяна) правила содержат детальное описание «что умеет и что знает»: When to use, Positioning, Core principles, Responsibilities, Artifacts, Workflow (по образцу .cursor/rules2). Новый сотрудник — добавить в employees.json, затем `python scripts/sync_employees.py`.
- **Тесты и верификация:** [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) (раздел 1 — пункты по области: воркер/Ollama 14–19, чат 21, Совет Директоров 36). После изменений в воркере/Ollama/LLM/делегировании/чате/Совете — пройти соответствующие пункты §1, прогнать тесты (`knowledge_os`: `pytest tests/test_json_fast_http_client.py tests/test_rest_api.py tests/test_victoria_chat_and_request.py -v`) и при необходимости обновить §3 или §5 чеклиста и CURRENT_STATE_WORKER_AND_LLM.md. Чат с Victoria: контракт goal + project_context, fallback при недоступности, слот в with_victoria_slot (пункт 21).

---

## 7. Конфигурация (ключевые переменные)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| USE_VICTORIA_ENHANCED | true | Включить Victoria Enhanced (ReAct, Department Heads, делегирование). |
| ENABLE_EVENT_MONITORING | true | Включить Victoria Initiative (Event Bus, мониторинг, skills). |
| PREFER_EXPERTS_FIRST | true | Execution-задачи в Victoria Enhanced, в Veronica — только простые. |
| SMART_WORKER_STUCK_MINUTES | 15 | Через сколько минут задача в in_progress без обновления updated_at считается зависшей. |
| SMART_WORKER_MAX_CONCURRENT | 15 | Потолок: макс. задач «в работе» одновременно. |
| SMART_WORKER_ADAPTIVE_CONCURRENCY | true | При true — effective_N по CPU/RAM и MLX/Ollama (потолок MAX_CONCURRENT); при false — фиксированный N. |
| ADAPTIVE_MLX_SAFE_MAX | 2 | Потолок одновременных запросов к MLX со стороны воркера (MLX вылетает при высоком параллелизме). |
| SMART_WORKER_BATCH_BY_MODEL | true | Батчировать задачи по (source, model). |
| SMART_WORKER_HEAVY_LIGHT_PAIRING | true | 50/50 MLX/Ollama + тяжёлый/лёгкий pairing: когда Ollama тяжёлая — MLX лёгкая, и наоборот. false = intelligent_model_router по сложности. |
| SMART_WORKER_INTERLEAVE_BLOCKS | true | Чередовать блоки (MLX и Ollama одновременно); при pairing — тяжёлый на одном, лёгкий на другом. |
| SMART_WORKER_HEAVY_MODEL_TIMEOUT_MULTIPLIER | 1.5 | Для тяжёлых моделей (70b, 104b, 32b) — множитель таймаута. Учитывает время загрузки (30–90 сек). |
| OLLAMA_API_URL, MLX_API_URL | host.docker.internal / localhost | URL Ollama и MLX. |
| DATABASE_URL | postgresql://...knowledge_postgres:5432/knowledge_os | БД Knowledge OS. |
| MAX_CONCURRENT_VICTORIA | 50 | Семафор запросов к Victoria в backend. |
| VICTORIA_MAX_STEPS_CHAT | 50 | Лимит шагов Victoria для чата (backend). Меньше «превышен лимит 500» и долгих ответов на локальных моделях. |
| VICTORIA_MAX_STEPS | 50 (Telegram) | Лимит шагов в Telegram-боте Victoria; на сервере по умолчанию 500 (если клиент не передаёт max_steps). |
| **VICTORIA_TIMEOUT** | **900** | Таймаут ожидания ответа Victoria (сек). 900 с = 15 мин — чтобы не обрывать сложные запросы на локальных моделях. |
| **OLLAMA_EXECUTOR_TIMEOUT** | **300** | Таймаут одного вызова Ollama в Victoria (сек). 300 с на каждый шаг LLM. |
| RAG_CONTEXT_LIMIT | 5 | Макс. узлов знаний в контексте Victoria. |
| RAG_SIMILARITY_THRESHOLD | 0.6 | Порог similarity для включения узла в контекст (RAG). |
| RAG_SNIPPET_CHARS | 500 | Символов на узел в контексте (сниппет). Раньше 200. |
| RAG_TOP1_FULL_MAX_CHARS | 2000 | Для топ-1 по similarity — полный контент до этого лимита; 0 = отключено. |
| AUTO_APPLY_DASHBOARD | false | При true — Dashboard Daily Improver авто-патчит max_entries в st.cache_data (Living Organism §3). |
| PREDICTIVE_STUCK_COUNT_THRESHOLD | 5 | Порог: при in_progress без обновления >15 мин ≥ N — создаётся задача. |
| PREDICTIVE_PENDING_COUNT_THRESHOLD | 30 | Порог: при pending старше 1ч ≥ N — создаётся задача. |
| BATCH_SMALL_TASKS_ENABLED | true (docker) | При true — Phase 1.6 помечает задачи одного domain (low/medium) batch_group. |
| BATCH_SMALL_TASKS_THRESHOLD | 3 | Мин. задач в domain для batch_group. |
| SMART_WORKER_BATCH_GROUP_LLM | true (docker) | При true — воркер обрабатывает задачи с batch_group одним вызовом LLM (2–3 на батч). |
| SMART_WORKER_BATCH_GROUP_MAX | 3 | Макс. задач в одном батч-вызове LLM. |

---

## 8. Таблица документов (где что искать)

| Тема | Документ |
|------|----------|
| Архитектура, порты, запуск | [PROJECT_ARCHITECTURE_AND_GUIDE.md](PROJECT_ARCHITECTURE_AND_GUIDE.md) |
| Границы src/ и knowledge_os (дублирование кода) | [SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md](SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md) |
| Схема Victoria → оркестратор → эксперты → воркер | [ARCHITECTURE_FULL.md](ARCHITECTURE_FULL.md) |
| Процесс Victoria от запроса до ответа | [VICTORIA_PROCESS_FULL.md](VICTORIA_PROCESS_FULL.md) |
| Воркер: пропускная способность, зависания, батчи | [WORKER_THROUGHPUT_AND_STUCK_TASKS.md](WORKER_THROUGHPUT_AND_STUCK_TASKS.md) |
| Ollama/MLX: URL, эхо, сканер | [OLLAMA_MLX_CONNECTION_AND_ECHO.md](OLLAMA_MLX_CONNECTION_AND_ECHO.md) |
| MLX API: порт 11435, скрипты, мониторинг | [MLX_API_SERVER_PORT_UPDATE.md](MLX_API_SERVER_PORT_UPDATE.md) |
| Текущее состояние воркера и LLM | [CURRENT_STATE_WORKER_AND_LLM.md](CURRENT_STATE_WORKER_AND_LLM.md) |
| Чеклист верификации (1–24), причины сбоев, при следующих изменениях | [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) |
| Сводка изменений из чатов | [CHANGES_FROM_OTHER_CHATS.md](CHANGES_FROM_OTHER_CHATS.md) |
| Дашборды и агенты (полная картина) | [DASHBOARDS_AND_AGENTS_FULL_PICTURE.md](DASHBOARDS_AND_AGENTS_FULL_PICTURE.md) |
| Роль Veronica, PREFER_EXPERTS_FIRST | [VERONICA_REAL_ROLE.md](VERONICA_REAL_ROLE.md) |
| Чат и оркестратор | [CHAT_ORCHESTRATOR_FLOW.md](CHAT_ORCHESTRATOR_FLOW.md) |
| Совет Директоров: чат → board/consult → Victoria | §3б этого документа; [CHANGES_FROM_OTHER_CHATS.md](CHANGES_FROM_OTHER_CHATS.md) §11 |
| **Авто-расчёт параллелизма воркера (CPU/память, MLX+Ollama, тяжёлые/лёгкие)** | [ADAPTIVE_WORKER_CONCURRENCY_PLAN.md](ADAPTIVE_WORKER_CONCURRENCY_PLAN.md) |
| Гипотезы, дебаты, цепочка гипотеза → дебат → задача | [HYPOTHESES_SYSTEM_STATUS.md](mac-studio/HYPOTHESES_SYSTEM_STATUS.md) |
| Календарь автономных циклов (что когда как) | [CORPORATION_PLANNING_CALENDAR.md](CORPORATION_PLANNING_CALENDAR.md) |
| Авто-профилирование (cProfile, py-spy) — Living Brain §6.3 | [AUTO_PROFILING_GUIDE.md](AUTO_PROFILING_GUIDE.md) |
| Grafana (настройка) | [GRAFANA_SETUP.md](GRAFANA_SETUP.md) |
| План верификации и полная хронология | .cursor/plans/VERIFICATION_AND_FULL_PICTURE_PLAN.md |
| **Корпорация на Rust: дорожная карта (видение, фазы, принципы)** | [CORPORATION_RUST_ROADMAP.md](CORPORATION_RUST_ROADMAP.md) |
| Оптимизации и кандидаты на Rust (cache_normalizer, порядок перевода) | [OPTIMIZATION_AND_RUST_CANDIDATES.md](OPTIMIZATION_AND_RUST_CANDIDATES.md) |
| Архив (исторические отчёты из корня) | [archive/README.md](archive/README.md) |
| **Планы и отчёты (единый индекс)** | [PLANS_AND_REPORTS_INDEX.md](PLANS_AND_REPORTS_INDEX.md) — .cursor/plans/, docs/archive/, learning_programs/, ai_insights/ |
| **Проект Сетки 21 (регистрация, .env)** | [PROJECT_SETKI_21_SETUP.md](PROJECT_SETKI_21_SETUP.md) |
| Оркестратор 137 (OOM), Ollama недоступен, живой организм | [ORCHESTRATOR_137_AND_OLLAMA.md](ORCHESTRATOR_137_AND_OLLAMA.md) |
| Victoria постоянно вылетает (ложный down, OOM) | [VICTORIA_RESTARTS_CAUSE.md](VICTORIA_RESTARTS_CAUSE.md) |
| Mac Studio: характеристики, загрузка, настройки Victoria/Backend | [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md) |
| Копия «тебя» на Mac Studio: статус и следующие шаги | [MAC_STUDIO_COPY_STATUS.md](MAC_STUDIO_COPY_STATUS.md) — что есть, чем продолжить (куратор, эталоны, план). |
| Время по моделям (загрузка, ответ): у каждой модели своё время, таймауты | [MODEL_TIMING_REFERENCE.md](MODEL_TIMING_REFERENCE.md) |
| **Холодный старт моделей (Ollama 8, MLX 11): замеры, таблицы, таймауты** | [MODEL_COLD_START_REFERENCE.md](MODEL_COLD_START_REFERENCE.md). Данные: **configs/ollama_model_timings.json**, **configs/mlx_model_timings.json**. Скрипт: `scripts/measure_cold_start_all_models.py` (MEASURE_SOURCE=ollama|mlx|all). |
| Предотвращение повторения: задачи не создаются, оркестратор 137 | [LIVING_ORGANISM_PREVENTION.md](LIVING_ORGANISM_PREVENTION.md) |
| Выявленные проблемы и решения с привлечением экспертов | [PROBLEMS_AND_EXPERT_SOLUTIONS.md](PROBLEMS_AND_EXPERT_SOLUTIONS.md) |
| Куратор Victoria и корпорации (Mac Studio) | [VICTORIA_CURATOR_PLAN.md](VICTORIA_CURATOR_PLAN.md) — постановка задач, проверка цепочки, наставник, эталоны |
| Чеклист куратора при разборе отчётов | [curator_reports/CURATOR_CHECKLIST.md](curator_reports/CURATOR_CHECKLIST.md) |
| Runbook куратора (прогон → чеклист → RAG) | [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) |
| Сбои «список файлов» в кураторе (connection reset, при следующих) | [curator_reports/CURATOR_LIST_FILES_FAILURES.md](curator_reports/CURATOR_LIST_FILES_FAILURES.md) |
| **Полная цепочка задачи Victoria** (кто распределяет, кто исполняет, один эксперт или команда, возврат) | [VICTORIA_TASK_CHAIN_FULL.md](VICTORIA_TASK_CHAIN_FULL.md) |
| **Тестирование всей системы** (Victoria, Veronica, оркестраторы, эксперты; как запускать; run_all_system_tests.sh) | [TESTING_FULL_SYSTEM.md](TESTING_FULL_SYSTEM.md) |
| **Подключение экспертов: источник, sync, БД, потребители, TTL, runbook** | [EXPERT_CONNECTION_ARCHITECTURE.md](EXPERT_CONNECTION_ARCHITECTURE.md) |
| **Использование базы знаний (Victoria, Veronica, оркестраторы, эксперты)** | [KNOWLEDGE_BASE_USAGE.md](KNOWLEDGE_BASE_USAGE.md) |
| **Как что делать (единый индекс для команды и агентов)** | [HOW_TO_INDEX.md](HOW_TO_INDEX.md) |
| **Как мы мыслим: подход и логика обработки задач** | [THINKING_AND_APPROACH.md](THINKING_AND_APPROACH.md) |
| **Проверка корпорации (пошагово, причина — как нужно — переделать)** | [CORPORATION_CHECK.md](CORPORATION_CHECK.md) |
| **Дорожная карта: когда корпорация станет «как я», что дальше по плану** | [ROADMAP_CORPORATION_LIKE_AI.md](ROADMAP_CORPORATION_LIKE_AI.md) |
| **Что не сделано и недоделано (единый список)** | [WHATS_NOT_DONE.md](WHATS_NOT_DONE.md) |
| Следующие шаги (RAG Redis, эталоны, улучшения) | [NEXT_STEPS_CORPORATION.md](NEXT_STEPS_CORPORATION.md) |
| **Contributing Guide (для команды)** | [CONTRIBUTING.md](../CONTRIBUTING.md) — запуск, тесты, E2E, методология, эксперты, развитие Victoria, TODO backlog. |
| **Ручные проверки (эхо/503, делегирование, Grafana, launchd)** | [MANUAL_VERIFICATION_CHECKLIST.md](MANUAL_VERIFICATION_CHECKLIST.md) — по желанию после изменений или перед релизом. |

---

---

## 10. Последние исправления (2026-02-14)
- **Singularity 14.0 — Полная Автономность и Самоэволюция:**
  - **Self-Evolution (Meta-Programming Loop):** Внедрен цикл автономного профилирования (`ArchitectureProfiler`), генерации гипотез и горячей замены кода (`promote_mutation`). Система теперь может сама переписывать свое ядро `ai_core.py`.
  - **Autonomous Sandboxes:** Агенты получили возможность самостоятельно деплоить микросервисы в изолированных Docker-контейнерах через `SandboxManager`.
  - **Global GraphRAG:** Переход от векторного поиска к графовому. Система извлекает сущности и связи, выполняя multi-hop рассуждения по всей базе знаний (86 экспертов).
  - **vLLM-level Inference:** Оптимизация локального инференса на Mac Studio (Continuous Batching, имитация PagedAttention через Metal cache clear).
  - **Cross-Container Self-Diagnosis:** Система автоматически выявляет «агрессивные» контейнеры по метрикам CPU/Net и может изолировать их в карантинную сеть.
  - **Multi-Project Command Center:** Дашборд теперь поддерживает управление несколькими проектами (`setki-21`, `atra`, `atra-web-ide`) с честным маппингом путей и защитой системного контекста.
- **VIP Routing & DeepSeek-R1 Integration:**
  - **VIP-коридор:** Внедрена система приоритетной маршрутизации для Ивана (CEO) и Совета Директоров.
  - **DeepSeek-R1 (32B/14B):** Новые рассуждающие модели интегрированы как основной интеллект для стратегических задач.
  - **Strategic Board Upgrade:** Логика Совета в `strategic_board.py` переведена на VIP-маршрут с использованием `deepseek-r1:32b`.
  - **Heartbeat Streaming:** В `local_router.py` добавлен стриминг для VIP-запросов, предотвращающий таймауты при долгих рассуждениях (до 10 минут).
- **Dashboard Fixes:** Исправлены ошибки `FileNotFoundError` (docker) и `NameError` (pd), дашборд полностью стабилизирован.
- **Полная Автономность Эволюции (v2.3):**
  - Кнопка «Запустить рекурсивную мутацию» удалена из дашборда.
  - Процесс мутации и инъекции скиллов теперь на 100% автономен и интегрирован в ночной цикл обучения.
  - В дашборде добавлен статус «Автономной Эволюции», показывающий дату последней мутации и планы системы по улучшению ДНК.
- **Autonomous Talent Management (v2.2):** Корпорация сама решает, какие навыки нужны экспертам.
- **Expert DNA Editor (Dashboard):** Визуальный редактор промптов и Skill Hub.
- **Nightly Learning Upgrade (v2.0):** Phase 0, Adversarial Self-Play и Red Team Council.
- **Архитектура «Живого Организма» (Sentinel Framework):**
  - **Sentinel Framework:** Создан универсальный механизм проактивного поведения экспертов (`sentinel_framework.py`).
  - **Автономные Стражи:** Анна (QA), Роман (DB) и Максим (Security) теперь автоматически инициируют задачи при изменении кода, деградации БД или угрозах безопасности.
  - **Task Queue v2:** Асинхронная постановка задач через Redis Streams для всех экспертов.
  - **OKR «Независимость»:** Добавлена стратегическая цель по Offline-First работе на Mac Studio.
- **Expert Evolution Fix:** Скрипт `expert_evolver.py` поддерживает точечную мутацию через `--expert_name`.

---

## 11. Что перезагрузить после изменений

---

## 11. Что перезагрузить после изменений

| Что меняли | Что перезагрузить / проверить |
|------------|-------------------------------|
| MLX API (падение, Metal OOM) | Мониторинг перезапускает автоматически (com.atra.mlx-monitor). Ручной перезапуск: `bash scripts/start_mlx_api_server.sh`. Проверка: `curl -s http://localhost:11435/health`. |
| Код воркера (smart_worker_autonomous, local_router, ai_core) | `docker compose -f knowledge_os/docker-compose.yml restart knowledge_os_worker` |
| Код Victoria / Veronica | `docker compose -f knowledge_os/docker-compose.yml restart victoria-agent veronica-agent` |
| Provisioning Grafana (dashboard.yml, datasources, JSON) | `docker compose restart grafana` (Web IDE) или `docker compose -f knowledge_os/docker-compose.yml restart grafana` (Knowledge OS). После рестарта дашборды подхватываются из папок «Web IDE» / «Knowledge OS» в левой панели. |
| Backend (config, routers) | `docker compose restart backend` или перезапуск uvicorn |
| Реестр проектов (таблица projects) | Рестарт Victoria/Veronica чтобы подхватить новый slug: `docker compose -f knowledge_os/docker-compose.yml restart victoria-agent veronica-agent`. Либо подождать TTL кэша (при реализации обновления кэша по времени). |
| Полный перезапуск стека | Сначала Knowledge OS: `docker compose -f knowledge_os/docker-compose.yml up -d`; через 15–20 сек Web IDE: `docker compose up -d`. Проверка: `curl -s http://localhost:8080/health`, `curl -s http://localhost:8010/status`. |

---

*При любых изменениях в архитектуре, логике, компонентах или подходах — обновлять этот документ и соответствующий раздел. Документ всегда актуален.*
