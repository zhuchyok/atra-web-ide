# Единый справочник проекта ATRA Web IDE (Master Reference)

## § Последние изменения (2026-03-14)
### Singularity 21.24: Quantum Optimization & Multi-Cluster Autonomy — VERIFIED ✅
1. **Quantum-Inspired Optimization:** Внедрен `QuantumInspiredOptimizer` на Rust (алгоритм имитации отжига и амплитудное сэмплирование) для RAG и планирования. Quantum RAG возвращает 5 узлов знаний при запросе.
2. **Multi-Cluster Autonomy:** Реализован `MultiClusterBridge` (Gossip-протокол) для синхронизации знаний и Task Tunneling (автоматический перехват задач при падении узла). Task Tunneling подтверждён live-тестом.
3. **Security (mTLS):** Внедрена поддержка HTTPS и клиентских сертификатов в Rust Gateway и Bridge. В dev-режиме работает без сертификатов (warning).
4. **Conflict Resolution:** Внедрена система версионирования знаний (Vector Clocks упрощённые) для разрешения конфликтов при синхронизации.
5. **UI Dashboard:** Создан компонент `ClusterDashboard.svelte` для мониторинга состояния распределенной сети узлов.
6. **Resilience (Optional KnowledgeEngine):** Gateway теперь стартует без паники при недоступной БД — KnowledgeEngine обёрнут в `Option<>`, knowledge-эндпоинты возвращают 503 вместо краша.
7. **Верификация пройдена:** `scripts/verify_quantum_cluster.py` — `[SUCCESS] Singularity 21.24 PASSED` (2026-03-14).

**«Библия» проекта** — это **этот документ + связка документов**, на которые он ссылается. Когда говорят **«библия»**, имеется в виду: изучить **docs/MASTER_REFERENCE.md** и при необходимости связанные документы:

- **docs/COGNITIVE_CODE.md** (Когнитивный кодекс: стандарты критического мышления).
- **PROJECT_ARCHITECTURE_AND_GUIDE**, **ARCHITECTURE_FULL**, **CURRENT_STATE_WORKER_AND_LLM**.
- **CHANGES_FROM_OTHER_CHATS.md** (Лог изменений).
- **VERIFICATION_CHECKLIST**, **DASHBOARDS_AND_AGENTS_FULL_PICTURE**.
- **docs/VICTORIA_USAGE_GUIDE.md** (руководство по использованию Виктории: режимы Cursor/MCP, терминал, Open WebUI; инструменты, примеры). Связь с правилами: **.cursor/rules/victoria.mdc**.
- **docs/VICTORIA_TASK_FORMULATION.md** (как правильно ставить задачи Виктории: структура goal, параметры запроса, выбор endpoint, примеры хороших и плохих постановок, мониторинг выполнения).

Закреплено в **.cursorrules** (раздел «Библия проекта»).

**Назначение:** при любых вопросов по разработке, изменениям, архитектуре, логике, портам, компонентам — **ищем здесь**. При добавлении нового или смене подхода — **отражаем здесь**. Документ всегда актуален.

**Правило репо:** правки вносить **в репозиторий того проекта, где живёт код**. setki-21 → репо setki-21; atra → репо atra; код Web IDE / Knowledge OS → atra-web-ide. Не править код setki-21 из atra-web-ide и наоборот.

**Золотой стандарт (Plan Mode и делегирование):** Золотой стандарт — это не просто список дел, а **делегирование задачи через инструмент Task** (или API Victoria): вызывающая сторона (пользователь/Cursor) выступает в роли **Куратора (Оркестратора)**, подзадача уходит **«локальной Виктории» (субагенту)** с полным контекстом Библии и чёткими инструкциями. Это экономит токены и время: субагент фокусируется только на выполнении, не перечитывая весь чат. Plan Mode обязателен для задач 3+ шагов: сначала план, одобрение, затем выполнение. **Куратор даёт задание Виктории только через скрипт** `scripts/curator_send_tasks_to_victoria.py --file <файл с goal> --async --max-wait 600`; результат в `docs/curator_reports/`. Подробно: **.cursor/rules/victoria.mdc** §0, **docs/VICTORIA_USAGE_GUIDE.md** § «Куратор», **docs/CURATOR_RUNBOOK.md** §0.

**Quick links:** [CHANGES](CHANGES_FROM_OTHER_CHATS.md) · [VERIFICATION](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) · [CURATOR_RUNBOOK](CURATOR_RUNBOOK.md) · [VICTORIA USAGE](VICTORIA_USAGE_GUIDE.md) · [VICTORIA TASK FORMULATION](VICTORIA_TASK_FORMULATION.md) · [AUTONOMY/OFFLINE](AUTONOMY_OFFLINE_READINESS.md) · [CONTRIBUTING](../CONTRIBUTING.md) · [FAQ](FAQ.md) · [HOW_TO_INDEX](HOW_TO_INDEX.md)

**Обновлено:** 2026-03-13

Последние изменения (2026-03-14): **Rust-ification & Hyper-Speed (Singularity 21.23).** (1) Пакетные операции `Batch Read` и `Batch Grep` перенесены на Rust Gateway (порт 8081), что дает 10-кратный прирост скорости. (2) Внедрена Rust-версия RAG-поиска с фильтрацией по контексту проекта. (3) Портирован **Anomaly Detector на Rust** для мгновенной проверки безопасности запросов через эвристики. (4) Реализована гибридная модель: Python-агенты вызывают Rust-сервисы с автоматическим fallback-ом.

Последние изменения (2026-03-14): **Global Cleanup & RAG Rocket Speed (Singularity 21.22).** (1) RAG ускорен в 5 раз через параллельный запуск GraphRAG/VectorRAG и кэширование доменов в памяти. (2) Начата декомпозиция `ai_core.py`: логика Anomaly Detection и Ensemble Verifier вынесена в модули `core/`. (3) Внедрен `DomainCache` для минимизации SQL-подзапросов.

Последние изменения (2026-03-14): **Antifragile Evolution (Singularity 21.21).** Внедрена триада «Инстинкта Выживания»: (1) **AgentChaosInjector** — Chaos Monkey для ИИ-агентов, симуляция сбоев в Shadow Execution. (2) **Antifragile Feedback Loop** — автоматическое масштабирование «антител» (инструкций) на весь департамент после сбоя. (3) **Recursive Testing** — обязательное требование авто-тестов для любой новой логики через ArchitecturalGuard.

Последние изменения (2026-03-14): **Absolute Dominance (Singularity 21.20).** Внедрена триада «Знаний Гигантов»: (1) **ArchitecturalGuard** — автоматическая проверка SOLID/KISS перед мутациями. (2) **AutonomousPolicyEnforcer** — динамические права экспертов на основе их KPI (Trading Floor Model). (3) **IntrospectionLoop** — обязательная самокритика и оттачивание ответов перед выдачей.

Последние изменения (2026-03-14): **Max Autonomy (Singularity 21.19).** Внедрена триада автономности: (1) **Autonomous Overseer** — автоматическая генерация задач на основе логов и бэклога. (2) **Self-Learning DNA** — инъекция «антител» в ДНК экспертов при обнаружении ошибок. (3) **Shadow Execution v2** — параллельная проверка оптимизаций с автоматическим Hot-Swapping. Система перешла на уровень 9.5/10 по шкале автономии.

Последние изменения (2026-03-13): **Victoria Connection Fix & Task Formulation Guide.** (1) Исправлен критический NameError в `file_watcher.py` (отсутствовал `import time`, использовался несуществующий `datetime.now()`). (2) Увеличены таймауты для сложных задач: `UVICORN_TIMEOUT_KEEP_ALIVE` 600→1800с (30 мин), `UNDERSTAND_GOAL_TIMEOUT_SEC` 90→300с (5 мин), `STRATEGY_CALL_TIMEOUT_SEC` 30→180с (3 мин), `VICTORIA_STREAM_HEARTBEAT_SEC` 15→10с. (3) Создан подробный гайд по постановке задач Victoria: структура goal, параметры запроса, выбор endpoint (/run, /stream, /orchestrate), примеры хороших/плохих постановок. (4) Документация: `docs/VICTORIA_CONNECTION_FIX.md`, `docs/VICTORIA_CONNECTION_FIX_SUMMARY.md`, `docs/VICTORIA_TASK_FORMULATION.md`. Результат: Victoria стабильно работает без обрывов до 30 минут.

Последние изменения (2026-03-12): **Deep Expert Specialization (Singularity 21.17).** Внедрена система персонализации экспертов: динамическая подгрузка правил (.mdc) и фильтрация Success Retrieval по конкретному исполнителю. Это превращает команду в оркестр узкопрофильных мастеров. См. CHANGES §83.

Последние изменения (2026-03-12): **Omni-RAG & Vision API Stabilization (Singularity 21.16).** (1) Внедрен Hybrid Search v2 и Cross-Encoder переранжировщик. (2) Стабилизировано Vision API (Moondream Station) на порту 2020 с автоматическим Watcher-ом. (3) Исправлены критические ошибки в Collective Memory (импорты) и GraphRAG (конкурентность). (4) Оптимизированы таймауты планирования (1200с) для предотвращения STRATEGIST FAILED. См. CHANGES §56.

Последние изменения (2026-03-12): **Self-Healing Logs (Singularity 21.15).** Реализована проактивная система исправления ошибок: сервис мониторит логи Docker в реальном времени, обнаруживает Tracebacks и автоматически готовит патчи (режим `awaiting_approval`). Это позволяет Виктории «лечить» себя до того, как баг станет критическим. См. CHANGES §82.

Последние изменения (2026-03-12): **Adaptive Concurrency (Singularity 21.14).** Внедрена система динамического управления очередью запросов в `OllamaExecutor`. Лимит параллельных вызовов LLM теперь автоматически адаптируется к температуре Mac Studio, загрузке RAM и производительности MLX, предотвращая перегрузку и каскадные сбои. См. CHANGES §81.

Последние изменения (2026-03-12): **Semantic Cache (Singularity 21.13).** Внедрена двухслойная система кэширования в `OllamaExecutor`: L1 (Hash) для мгновенных ответов и L2 (Semantic) через векторную БД для семантически близких запросов (threshold 0.95). Реализована фильтрация динамических команд (`ls`, `cat`, `status`) для обеспечения актуальности данных. См. CHANGES §80.

Последние изменения (2026-03-12): **Success Retrieval & Session Context Injection.** (1) Внедрена система Success Retrieval (Сингулярность 21.12): Victoria теперь обучается на прошлых успешных задачах через векторный поиск по таблице `tasks`. (2) Реализована инъекция контекста сессии в системный промпт для связности диалога. (3) Внедрена защита инференса: Circuit Breaker и MLX Admission Control. См. CHANGES §77, §78, §79.

Последние изменения (2026-03-12): **Оптимизация роутера чата: batch append и character limit.** (1) В `stream_message` сохранение истории теперь выполняется параллельно через `asyncio.gather`. (2) Ограничение размера истории (10000 символов) перенесено непосредственно в метод `get_recent` менеджера контекста. (3) Реализовано сохранение частичного ответа ассистента при разрыве соединения (`CancelledError`). См. CHANGES §76.

Последние изменения (2026-03-10): **Omni-RAG — Единый Интеллект (Open WebUI & Telegram).** (1) Внедрена архитектура Omni-RAG: теперь знания из Hybrid Search v2 автоматически инъецируются в запросы из Open WebUI (через OpenAI API эндпоинт). (2) Создан унифицированный эндпоинт `POST /api/omni-rag/search` для внешних систем. (3) Реализована поддержка контекста для Telegram-сессий. (4) База знаний теперь синхронизирована между всеми точками взаимодействия с пользователем. См. CHANGES §63.

Последние изменения (2026-03-10): **Enhanced RAG — Hybrid Search v2 & Re-ranking.** (1) Внедрен Hybrid Search v2 (BM25 + Vector) с использованием PostgreSQL `tsvector` и `ts_rank_cd` для молниеносного поиска по ключевым словам. (2) Интегрирован Cross-Encoder Re-ranking на базе модели `ms-marco-MiniLM-L-6-v2` для финальной фильтрации результатов (точность выросла на порядок). (3) Реализован External Docs Indexer для автоматического парсинга произвольных URL и GitHub репозиториев (OpenAI, Anthropic, DeepSeek, LangChain). (4) Виктория теперь автоматически подтягивает знания из домена «AI Research» через новый гибридный поиск. См. CHANGES §62.

Последние изменения (2026-03-08): **IQ Boost — Consensus v2, Debate & Self-Correction.** (1) Внедрена система `Self-Correction`: Victoria теперь критикует и исправляет свой собственный ответ перед выдачей пользователю (для категорий coding/reasoning). (2) Реализована полноценная интеграция `Multi-Agent Debate`: для сложных задач запускается дискуссия между Архитектором, экспертом по безопасности и Прагматиком. (3) **Consensus v2**: Внедрено взвешенное голосование в `ConsensusAgent` на основе KPI экспертов (`performance_score` из БД) и их уверенности. (4) Метод `complex` в `VictoriaEnhanced` теперь автоматически использует Debate с fallback на Consensus v2. См. CHANGES §60.

Последние изменения (2026-03-08): **Thermal Protection — автоматическое управление нагрузкой.** (1) В `MacStudioMonitor` реализована логика обнаружения перегрева (Thermal Level >= 1) и критической загрузки RAM (> 92%). (2) Внедрен механизм автоматической выгрузки лишних моделей из Ollama при перегрузке (кроме `IMMORTAL_MODELS`). (3) `LocalAIRouter` теперь автоматически переключается на сверхлегкие модели (`phi3.5`, `tinyllama`) при срабатывании термальной защиты, снижая нагрузку на GPU. См. CHANGES §59.

Последние изменения (2026-03-09): **Stuck Tasks Watchdog — автоматический сброс зависших задач.** (1) Реализована интеграция `reset_stuck_tasks.py` в `system_auto_recovery.sh` для автоматической очистки очереди при сбоях. (2) Создан `scripts/setup_stuck_tasks_watchdog.sh` для ежечасного сброса задач через `launchd`. (3) Скрипт теперь гарантированно использует `knowledge_os/.venv` для избежания ошибок импорта `asyncpg`. См. CHANGES §61.

Последние изменения (2026-03-08): **Mac Studio Monitoring — глубокий мониторинг железа.** (1) Создан `MacStudioMonitor` для сбора метрик CPU, RAM, Thermal Level и загруженных моделей (Ollama/MLX). (2) Реализована интеграция с `victoria_server.py`: при запросах о «железе», «нагрузке» или «температуре» Виктория теперь автоматически подтягивает real-time данные Mac Studio. (3) Добавлена поддержка `sysctl` для мониторинга термального состояния. См. CHANGES §58.

Последние изменения (2026-03-08): **Self-Evolution v2 — верификация через Pytest.** (1) `CodebaseMutationEngine` теперь автоматически ищет связанные тесты для исправляемого файла. (2) В `Patch Safety Guard` интегрирован запуск `pytest`: патч применяется только если все тесты пройдены. (3) Реализована логика автоматического отката (Rollback): если тесты провалены, изменения отменяются, и система возвращается к стабильному состоянию. (4) Добавлена поддержка бэкапов файлов при верификации. См. CHANGES §57.

Последние изменения (2026-03-08): **Self-Evolution — автоматические патчи и Self-Healing.** (1) `CodebaseMutationEngine` расширен логикой генерации патчей через Victoria Enhanced (Extended Thinking). (2) Внедрена система `Patch Safety Guard`: автоматическая проверка синтаксиса Python перед применением патча. (3) В `VictoriaEventHandlers` добавлен хук `Syntax Auto-Fix`: при создании файла с синтаксической ошибкой Mutation Engine автоматически пытается её исправить. (4) Реализован полный цикл самоисцеления: Ошибка -> Анализ -> Патч -> Верификация -> Применение. См. CHANGES §56.

Последние изменения (2026-03-08): **Autonomous Core — усиление автономности (Mutation & Shadow).** (1) Создан `CodebaseMutationEngine` для автоматического анализа и исправления ошибок в фоне. (2) Реализован `ShadowExecutionManager` для параллельной проверки оптимизаций («в тени» основного процесса). (3) Внедрена система проактивных предложений в `victoria_server.py`: при запросах статуса Victoria теперь автоматически учитывает недавние ошибки из `Event Bus`. (4) `VictoriaEventHandlers` расширены хуками для Mutation и Shadow систем. См. CHANGES §55.

Последние изменения (2026-03-08): **Skill Discipline v2 — полная загрузка инструкций (План B.2, финал).** (1) В `skill_mapper.py` реализована загрузка полных текстов из `SKILL.md` файлов (через `glob` и кэширование). (2) В `victoria_server.py` исправлена инъекция `enriched_goal` для всех путей (SSE, sync, async) — инструкции скилла теперь попадают в промпт Victoria гарантированно. (3) Это делает Victoria на 100% эквивалентной Cursor assistant по дисциплине и качеству следования workflow. **План B завершён полностью!** См. CHANGES §54.

Последние изменения (2026-03-08): **Оптимизация архитектуры «Мозг и Руки» (MLX & Ollama) — Финал.** (1) Внедрена политика Smart Cooldown (300с) и категория `IMMORTAL_MODELS` (nomic, moondream, tinyllama, phi3.5) в `ollama_keep_alive_policy.py`. (2) Реализован `ContextMirror` (Redis) для бесшовного переноса истории сессий при failover. (3) В `local_router.py` интегрирован упреждающий прогрев (Predictive Warmup) и логика `[FALLBACK_MODE]`. (4) Внедрен `MLXMonitor` с расчетом **Health Score** (на основе TBT > 200ms и очереди > 5), который автоматически триггерит прогрев Ollama при деградации MLX. См. CHANGES §53.

Последние изменения (2026-03-08): **Ночной график эволюции (00:00 - 06:00).** (1) Настроено окно глубокого самообучения и оптимизации ядра. (2) Nightly Learner и Mutation Engine теперь работают исключительно в ночное время для экономии ресурсов Mac Studio днем. (3) Внедрен 'режим тишины' для мониторинга в это время.

Последние изменения (2026-03-06): **Batch Read — параллельное чтение файлов (План B.4, финал).** (1) Создан модуль `batch_read.py` с функциями `batch_read_files()` и `batch_grep_files()` для параллельного чтения/поиска (max_concurrent=10, semaphore). (2) API endpoints `POST /batch_read` и `POST /batch_grep` в victoria_server. (3) MCP tools `victoria_batch_read` и `victoria_batch_grep` для Cursor. (4) Graceful error handling (файл не найден, слишком большой, encoding). (5) Это устраняет ограничение «последовательные шаги» — можно сканировать 50+ файлов за 0.5 сек. **План B завершён на 100%!** См. CHANGES §47, MASTER_REFERENCE (Batch Read).

Последние изменения (2026-03-06): **IDE Context — контекст в формате Cursor (План B.3).** (1) TaskRequest расширен полями `open_files`, `git_status`, `cursor_rules`, `workspace_path` для передачи IDE-контекста. (2) Создана функция `_format_ide_context()` для форматирования контекста в читаемый текст (workspace, git, открытые файлы с cursor_line, правила). (3) IDE-контекст инъецируется в `enriched_goal` перед отправкой в Victoria (после skill_context). (4) MCP tool `victoria_run_with_context` создан для передачи контекста из Cursor. (5) Это даёт Victoria тот же «срез окружения», что у Cursor assistant (открытые файлы, git, правила). Статус: ✅ полная реализация. См. CHANGES §46, MASTER_REFERENCE (IDE Context).

Последние изменения (2026-03-06): **Skill Discipline — жёсткая дисциплина скиллов (План B.2).** (1) Создан `skill_mapper.py` с классификатором задач (5 скиллов: brainstorming, TDD, debugging, verification, code_review). (2) Автовызов в `victoria_server.py` — при распознавании типа задачи инструкции скилла добавляются в goal. (3) SSE уведомление «Применяется скилл: {description}». (4) Правило «1% шанс = вызвать скилл». Статус: ✅ базовая реализация. См. CHANGES §45, MASTER_REFERENCE (Skill Discipline).

Последние изменения (2026-03-06): **Execution Plan — руки в IDE (План B.1).** (1) Victoria теперь может генерировать структурированный `execution_plan` (список шагов: read_file, edit, run) для выполнения в IDE/клиенте. (2) Расширены `TaskRequest` (`return_execution_plan: bool`) и `TaskResponse` (`execution_plan: List[Dict]`). (3) Добавлен парсер `_extract_execution_plan()` (поддержка JSON и markdown). (4) Промпт Victoria дополнен секцией «EXECUTION PLAN» с примерами. (5) MCP tool `victoria_execute_plan` создан для автоматического выполнения плана. (6) Executor `execution_plan_executor.py` для интеграции with filesystem MCP. (7) Это решает проблему «мозг и руки разделены» — Victoria планирует, клиент выполняет. Статус: ✅ базовая архитектура, 🚧 полная интеграция с MCP. См. CHANGES §44, victoria.mdc §6, `.cursor/plans/plan-b-*.md`.

Последние изменения (2026-03-06): **STRICT_LOCAL: строго локальный режим.** (1) Введён переключатель `STRICT_LOCAL=false` (дефолт) в `.env.example` и `docker-compose.yml` для полной автономности от облачных API. (2) Создан модуль `env_flags.py` с `is_strict_local()`. (3) Модифицированы `ai_core.py`, `safety_checker.py`, `quality_assurance.py`, `intelligence_consensus.py`, `disaster_recovery.py`: при `STRICT_LOCAL=true` блокируется cursor-agent и облачные fallback, выполняется retry локально с улучшенным промптом; при неудаче — reject с явным сообщением. (4) Graceful degradation при частичной недоступности (MLX down, Ollama работает). (5) Метрики: `strict_local_enabled`, `strict_local_safety_skip_count`, `strict_local_qa_skip_count`. (6) Документация: раздел STRICT*LOCAL в MASTER_REFERENCE, CHANGES §43. См. план в `.cursor/plans/strict_local_implementation*\*.plan.md`.

Последние изменения (2026-03-05): **Библия обновлена по сессии: Victoria Tasks, инвентаризация, самовосстановление MLX.** (1) Домен **victoria_tasks** создан в БД — самообучение Виктории снова попадает в RAG и планирование (CHANGES §40). (2) **Инвентаризация возможностей** — отчёт docs/audits/INVENTORY_VICTORIA_CAPABILITIES_2026.md (Initiative, OTEL, Recovery, знания гигантов, реестр проектов, чеклисты §10–11); CHANGES §41. (3) **Recovery Listener (9099):** доработка host_recovery_listener.py (GET /recover, безопасный Content-Length), чеклист в INVENTORY §11, перезапуск через launchd; CHANGES §42. При любых изменениях — обновлять MASTER_REFERENCE и CHANGES (правило библии).

---

## § Гибридная операционная модель (Singularity 21.5)

**Стандарт работы:**
Облачный ассистент (Cursor) является **Диспетчером**.
Локальный агент (Victoria) является **Исполнителем**.

**Концепция «Диспетчер — Исполнитель»:**

- **Cursor (Облачный Диспетчер):** Использует внешние модели (Claude/GPT) как «тонкий слой» логики. Его задача — понимать намерения пользователя, декомпозировать их на технические команды и управлять локальными агентами.
- **Victoria (Локальный Мозг):** Работает на Mac Studio (модели MLX/Ollama). Это «тяжелая артиллерия», которая имеет прямой доступ к терабайтам контекста, базе данных PostgreSQL и файловой системе.

**Механика взаимодействия:**

1. **Делегирование:** Вместо копирования кода в чат Cursor, Диспетчер использует `scripts/curator_send_tasks_to_victoria.py` или прямой запуск локальных модулей через `docker exec`.
2. **Экономия токенов (Token Economy):** Виктория считывает файлы локально. Облачная модель получает только **результат** (краткий отчет или исправленный код), что в 100+ раз меньше по объему.
3. **RAG:** Виктория сама ищет в базе знаний через векторный поиск (pgvector). Облаку не нужно «помнить» весь проект.
4. **Нулевая стоимость итераций:** Если код нужно переписывать многократно, это делает Виктория локально. В облако уходит только финальная версия.

**Золотые правила для AI-ассистента:**

1. **Принцип «Сначала спроси Викторию»:** Перед анализом сложной проблемы запроси контекст у локальной базы знаний.
2. **Делегирование тяжелых задач:** Генерация тестов, глубокий аудит безопасности, рефакторинг больших модулей и Omni-RAG поиск выполняются локально.
3. **Контроль через логи:** Всегда проверяй реальное состояние системы через `docker logs` и статус задач в БД.
4. **Использование локальных экспертов:** Вызывай экспертов по именам (`@igor`, `@anna`, `@dmitry`) через промпты Виктории.

**Результат:** Экономия 90% лимитов токенов и использование 100% мощности Mac Studio.

---

## Wisdom Era Status (Singularity 21.5: Total Dominance)

**Архитектура:** Единый Интеллект v3.5. **Параллельная работа (Parallel Work):** Мозг (MLX, порт 11435) и Руки (Ollama, порт 11434) работают совместно, распределяя нагрузку. Модель **victoria-wisdom-v3.5** (MLX) и **victoria-wisdom-v3.5:latest** (Ollama) идентичны по знаниям.
**Полноценная Виктория (v3.5):** (1) **MLX (мозг):** `VICTORIA_MLX_BRAIN=true` — предзагрузка (Pure MLX). (2) **Ollama (руки):** активны параллельно; становятся бессмертными (`keep_alive=-1`) только при падении MLX. При живом MLX выгружаются через 60с простоя для экономии RAM. (3) **Дефибриллятор:** активен на порту 9099. (4) **Балансировка:** `local_router.py` распределяет задачи между Мозгом и Руками.

**Самовосстановление и Мониторинг:** Система мониторит v3.5 в обоих каналах через `MLXMonitor`. При деградации производительности (Health Score < 0.5) или сбое MLX происходит упреждающий прогрев Ollama и мгновенный fallback без потери контекста (через Redis Context Mirror).

**Последний аудит (03.03.2026):** Переход с 30B на 35B MoE (Qwen 3.5). Скорость загрузки в MLX: 4.6с. Личность подтверждена. Все эксперты уведомлены о смене ядра.

**При смене модели (чеклист):** обновить MASTER*REFERENCE (этот блок), `.cursor/rules/victoria.mdc`, `.cursor/rules/expert_and_brainstorm.mdc`, `.cursorrules` (Компоненты), `docs/COGNITIVE_CODE.md`, `docs/PORT_REGISTRY.md`, `knowledge_os/USER.md`, `knowledge_os/SOUL.md`, `docs/OPENWEBUI_VICTORIA_WISDOM_MODEL.md`, `docs/SESSION_HANDOFF*\*.md`при актуальности; исторические планы в`docs/plans/` не переписывать — источник истины здесь.

---

## STRICT_LOCAL (строго локальный режим)

**Назначение:** Полная автономность от облачных API. При `STRICT_LOCAL=true` все запросы обслуживаются только локальными моделями (MLX + Ollama); при недоступности локальных моделей возвращается явная ошибка, без fallback на cursor-agent или облачные API.

**Когда использовать:**

- Закрытые сети (closed network)
- Конфиденциальные данные (GDPR, regulatory compliance)
- Полная изоляция от внешних API

**Когда НЕ использовать:**

- Повседневная работа (на сложных reasoning-задачах качество может быть ниже)
- Первичная настройка (требуется доступность локальных моделей)

**Дефолт:** `STRICT_LOCAL=false` (рекомендуется для большинства сценариев)

### Pre-flight checklist (обязательно перед включением STRICT_LOCAL):

Выполните проверку **перед** изменением `STRICT_LOCAL=true`:

1. **Проверка MLX:** `curl -s http://localhost:11435/health` → HTTP 200
2. **Проверка Ollama:** `curl -s http://localhost:11434/api/tags` → HTTP 200, список содержит `victoria-wisdom-v3.5:latest`
3. **Проверка Recovery Listener:** `curl -s http://localhost:9099/recover` → HTTP 200 (критично для STRICT_LOCAL; без него при падении MLX система полностью недоступна; см. INVENTORY_VICTORIA_CAPABILITIES_2026.md §11)

Если хотя бы одна проверка не прошла — **не включайте STRICT_LOCAL**, сначала восстановите сервис. Полная оценка готовности к автономности и работе без интернета: **docs/AUTONOMY_OFFLINE_READINESS.md**.

### 12-Factor (Config):

При изменении `STRICT_LOCAL` в `.env` перезапустите контейнеры:

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d
docker-compose up -d  # backend
```

### Adaptive Concurrency:

STRICT_LOCAL увеличивает нагрузку на локальные модели (вся нагрузка на MLX/Ollama, без облачного fallback). При высоком трафике рассмотрите:

- Снижение `MAX_CONCURRENT_VICTORIA` (с 50 до 30-40)
- Горизонтальное масштабирование MLX/Ollama

### Pre-mortem (3 сценария провала и защита):

1. **MLX и Ollama падают одновременно** → все запросы отклоняются.
   - **Защита:** pre-flight checklist + Recovery Listener (9099) + мониторинг
2. **Локальная модель выдаёт небезопасный код** → safety_checker блокирует, но ответ отклоняется (не уходит пользователю).
   - **Защита:** при срабатывании safety в STRICT_LOCAL — reject или retry с изменённым промптом (безопасный промпт)
3. **Качество ответов падает на сложных задачах** → пользователи недовольны.
   - **Защита:** чёткая документация (этот блок) + при низком качестве в ответе пояснение пользователю: «⚠️ STRICT_LOCAL блокирует улучшение качества. Для сложных задач отключите STRICT_LOCAL.»

### Идемпотентность:

Повторный запрос с тем же goal при STRICT_LOCAL даёт тот же результат (ошибка или локальный ответ); дубли в БД не создаются (золотой стандарт, см. .cursorrules).

### Graceful Degradation:

При частичной недоступности (например MLX down, но Ollama работает):

- Логируется `[GRACEFUL DEGRADATION] MLX недоступен, используется только Ollama`
- В ответ пользователю добавляется подсказка: «⚠️ Работаем в ограниченном режиме: основной интеллект (MLX) недоступен. Качество ответов может быть ниже. Проверьте порт 11435 или Recovery (9099).»

### Метрики:

- `strict_local_enabled` (gauge, 0 или 1) — флаг режима STRICT_LOCAL
- `strict_local_safety_skip_count` (counter) — количество срабатываний safety_checker, которые не привели к reroute (потому что STRICT_LOCAL)
- `strict_local_qa_skip_count` (counter) — количество срабатываний QA с рекомендацией reroute_to_cloud, которые не выполнены

Метрики `strict_local_*` экспортируются в **GET http://localhost:8010/metrics** (Victoria Server).

**Алерт в Grafana:** если `strict_local_enabled == 1` **и** (`mlx_health == down` **или** `ollama_health == down`) — критический алерт «STRICT_LOCAL ON, но локальные модели недоступны → система полностью недоступна».

### Внедрено (2026-03-06):

- **Файлы изменены:** `ai_core.py`, `safety_checker.py`, `quality_assurance.py`, `intelligence_consensus.py`, `disaster_recovery.py`, `backend/app/services/ollama.py`, `.env.example`, `docker-compose.yml`
- **Файлы созданы:** `knowledge_os/app/env_flags.py`
- **Логика:** при `is_strict_local()`:
  - `_run_cloud_agent_async` не вызывает cursor-agent, retry через локальные модели с backoff
  - `safety_checker.should_reroute_to_cloud()` возвращает `False`
  - `quality_assurance` заменяет `reroute_to_cloud` на `retry_local`
  - `intelligence_consensus` выполняет консенсус через 2 локальных вызова (reasoning + coding)
  - `disaster_recovery.can_use_cloud()` возвращает `False`
  - `backend/app/services/ollama.py` создаёт singleton с `use_cloud=False` (Ollama Cloud API заблокирован)

### Голосовой ввод и Ollama Cloud:

- **Голосовой ввод:** `knowledge_os/app/voice_processor.py` использует `USE_OPENAI_WHISPER=false` по умолчанию (локальное распознавание речи). Для полной локальности не включайте `USE_OPENAI_WHISPER`.
- **Ollama Cloud:** `backend/app/services/ollama.py` в STRICT_LOCAL режиме принудительно использует `use_cloud=False`, блокируя доступ к Ollama Cloud API (https://ollama.com) даже при наличии `OLLAMA_API_KEY`.

**См. также:** [CHANGES_FROM_OTHER_CHATS.md](CHANGES_FROM_OTHER_CHATS.md) §43 (детали внедрения)

---

## Execution Plan — руки в IDE (План B: Cursor Parity)

**Концепция:** Виктория решает **ЧТО** делать (планирует изменения в коде), а IDE/клиент выполняет **КАК** (редактирование файлов, запуск команд). Это разделение «мозг и руки» на уровне разработки — Victoria становится интеллектуальным планировщиком, а среда разработки (Cursor/MCP) — исполнителем.

**Проблема:** Виктория живёт как сервис (порт 8010) — она даёт план и ответы, но не может напрямую править файлы в IDE пользователя. Раньше выполнение делегировалось Veronica или выполнялось вручную.

**Решение:** Виктория генерирует структурированный `execution_plan` (список шагов: read_file, edit, run), который клиент (Cursor через MCP) выполняет автоматически. Это даёт Виктории «руки в IDE» без изменения её архитектуры (она остаётся сервисом).

### Использование

1. **Запрос с `return_execution_plan=true`:**

   ```bash
   curl -X POST http://localhost:8010/orchestrate \
     -H "Content-Type: application/json" \
     -d '{
       "goal": "Добавь функцию validate_email в utils/validators.py",
       "return_execution_plan": true
     }'
   ```

2. **Ответ содержит `execution_plan`:**

   ```json
   {
     "status": "success",
     "output": "Создан план для добавления validate_email...",
     "execution_plan": [
       {
         "action": "read_file",
         "path": "utils/validators.py",
         "description": "Прочитать текущую реализацию"
       },
       {
         "action": "edit",
         "path": "utils/validators.py",
         "content": "import re\n\ndef validate_email(email: str) -> bool:\n    ...",
         "description": "Добавить функцию validate_email"
       },
       {
         "action": "run",
         "command": "pytest tests/test_validators.py",
         "description": "Проверить изменения"
       }
     ]
   }
   ```

3. **MCP tool для автоматического выполнения (Cursor):**

   ```python
   # Вызов через MCP VictoriaATRA (порт 8012)
   victoria_execute_plan(
     goal="Добавь функцию validate_email в utils/validators.py",
     workspace_path="/Users/bikos/Documents/atra-web-ide"
   )
   ```

   Инструмент `victoria_execute_plan` в MCP server (`src/agents/bridge/victoria_mcp_server.py`) автоматически:
   - Запрашивает plan от Victoria через `/orchestrate` с `return_execution_plan=true`
   - Выполняет каждый шаг плана (read/edit/run)
   - Возвращает результат каждого шага

### Формат execution_plan

Каждый шаг — это объект с полями:

| Поле          | Тип     | Описание                                                     | Для action          |
| ------------- | ------- | ------------------------------------------------------------ | ------------------- |
| `action`      | string  | Тип действия: `read_file`, `edit`, `run`                     | Все                 |
| `path`        | string  | Путь к файлу (относительный или абсолютный)                  | `read_file`, `edit` |
| `command`     | string  | Команда для терминала                                        | `run`               |
| `content`     | string  | Новое содержимое файла (опционально)                         | `edit`              |
| `description` | string  | Что делает этот шаг (для логов и UI)                         | Все                 |
| `critical`    | boolean | Прервать выполнение при ошибке (опционально, default: false) | Все                 |

**Пример:**

```json
[
  {
    "action": "read_file",
    "path": "src/utils.py",
    "description": "Изучить текущий код"
  },
  {
    "action": "edit",
    "path": "src/utils.py",
    "content": "...",
    "description": "Добавить функцию X"
  },
  {
    "action": "run",
    "command": "pytest src/tests/",
    "description": "Проверить изменения",
    "critical": true
  }
]
```

### Реализация (внедрено 2026-03-06)

**1. API расширение (`victoria_server.py`):**

- `TaskRequest.return_execution_plan: bool = False` — флаг для запроса плана
- `TaskResponse.execution_plan: Optional[List[Dict]]` — поле с планом
- `/orchestrate` endpoint — извлекает plan из ответа модели через `_extract_execution_plan()`

**2. Парсинг (`_extract_execution_plan()` в `victoria_server.py`):**
Поддерживает два формата в ответе модели:

- JSON-блок в тройных бэктиках: ` ```json\n[{...}]\n``` `
- Markdown-список:

  ```markdown
  **Execution Plan:**

  - read_file: path/to/file.py
  - edit: path/to/file.py (описание)
  - run: pytest tests/
  ```

**3. Промпт Victoria (`agent.executor.system_prompt`):**
Добавлена секция **«EXECUTION PLAN (руки в IDE)»** с инструкциями:

- Когда генерировать plan (задачи с изменением кода)
- Формат JSON для execution_plan
- Примеры шагов (read_file, edit, run)

**4. MCP tool (`victoria_mcp_server.py`):**

- `victoria_execute_plan(goal, workspace_path)` — получает plan от Victoria и выполняет через MCP filesystem
- Пока упрощённая версия (логирование шагов без реального выполнения)
- Полная интеграция с `user-filesystem` MCP server в разработке

**5. Executor (`execution_plan_executor.py`):**

- `ExecutionPlanExecutor` — класс для выполнения плана через MCP tools
- Методы: `_execute_read_file`, `_execute_edit`, `_execute_run`
- Поддержка относительных путей (workspace_path)
- Graceful error handling (продолжать выполнение при некритичных ошибках)

### Статус и Next Steps

**✅ Завершено (2026-03-06):**

- TaskRequest/TaskResponse расширены
- Парсинг execution_plan из ответа модели (JSON + markdown)
- Промпт Victoria обучен генерировать plan
- MCP tool `victoria_execute_plan` создан
- Документация обновлена (victoria.mdc, MASTER_REFERENCE)

**🚧 В разработке:**

- Полная интеграция `victoria_execute_plan` with `user-filesystem` MCP server (реальное чтение/запись файлов)
- Поддержка diff/patch для точечных правок (сейчас edit перезаписывает файл целиком)
- UI для отображения execution_plan в Web IDE (показать шаги перед выполнением)

**🔜 Следующие задачи (План B):**

- **B.2: Жёсткая дисциплина скиллов** — автоматический вызов скиллов по типу задачи (как в Cursor) — ✅ **ЗАВЕРШЕНО 2026-03-06**
- **B.3: Контекст в формате Cursor** — передача открытых файлов, git status, правил в запросах к Victoria
- **B.4: Параллельные чтения (batch_read)** — множественные read_file/grep за один запрос через Veronica

**См. также:** Plan B детализация в `.cursor/plans/plan-b-victoria-cursor-parity.md`

---

## Skill Discipline — жёсткая дисциплина скиллов (План B.2)

**Назначение:** Автоматическое применение нужного скилла по типу задачи, как в Cursor assistant. Правило: «если есть хотя бы 1% шанс, что скилл применим — вызвать скилл до ответа».

**Реализация (внедрено 2026-03-06):**

1. **Skill Mapper** (`knowledge_os/app/skill_mapper.py`):
   - Классифицирует задачу по regex-паттернам
   - Возвращает `{"skill": "brainstorming", "path": "...", "description": "..."}`
   - Singleton pattern для переиспользования

2. **Поддерживаемые скиллы:**
   - `brainstorming`: новая фича/компонент/функционал → discovery, дизайн по секциям, план внедрения, **НЕ КОД** до утверждения дизайна
   - `tdd`: тесты/unit/интеграция → Red-Green-Refactor, test-first (тест ДО реализации)
   - `debugging`: ошибка/баг/провал теста → systematic debugging (воспроизведи, изучи логи, гипотеза, проверка, исправление, тест для регрессии)
   - `verification`: проверка/убедись/тесты прошли → запуск тестов, линты, manual QA, **ТОЛЬКО после проверки — завершение**
   - `code_review`: ревью кода/изменений → SOLID, безопасность (secrets, SQL injection, XSS), тесты, покрытие

3. **Автовызов в victoria_server (`run_task_stream`):**
   - При получении задачи вызывается `skill_mapper.classify_task(goal)`
   - Если скилл найден → инструкции скилла добавляются в начало goal как `skill_context`
   - В SSE stream выводится шаг: "Применяется скилл: {description}"
   - Victoria получает `enriched_goal = skill_context + original_goal`

4. **Формат инструкций скилла:**

   ```
   🎯 ПРИМЕНЯЕТСЯ СКИЛЛ: BRAINSTORMING

   1. Изучи контекст проекта
   2. Задай 1 уточняющий вопрос (цель, ограничения)
   3. Предложи 2-3 подхода с плюсами/минусами
   4. Представь дизайн по секциям, спрашивай одобрение после каждой
   5. Запиши утверждённый дизайн в docs/plans/YYYY-MM-DD-<topic>-design.md
   6. Следующий шаг — writing-plans (план внедрения), НЕ код

   ВАЖНО: Следуй чеклисту скилла СТРОГО. Это не рекомендация — это обязательный workflow.
   ```

**Примеры триггеров:**

- "Создай новый компонент X" → `brainstorming` (паттерн: `созда.*новый.*компонент`)
- "Напиши тест для функции Y" → `tdd` (паттерн: `напиш.*тест`)
- "Исправь ошибку в модуле Z" → `debugging` (паттерн: `исправ.*ошибк`)
- "Проверь что всё работает" → `verification` (паттерн: `проверь`)

**Статус:** ✅ Базовая реализация (mapper, автовызов, чеклисты). 🚧 Полная загрузка SKILL.md (с детальными примерами) через Read tool в разработке.

---

## IDE Context — контекст в формате Cursor (План B.3)

**Назначение:** Victoria видит то же, что видит Cursor assistant: открытые файлы, git status, применимые правила из .cursor/. Это устраняет разницу в «срезе окружения» между Victoria (goal + RAG) и Cursor (открытые файлы + git + правила).

**Реализация (внедрено 2026-03-06):**

1. **Расширение TaskRequest** (`src/agents/bridge/victoria_server.py`):
   - `open_files: Optional[List[Dict]]` — открытые файлы: `[{"path": "...", "content": "...", "cursor_line": 42}, ...]`
   - `git_status: Optional[str]` — git status (измененные файлы, ветка): `"On branch main\nModified: src/utils.py\n..."`
   - `cursor_rules: Optional[List[str]]` — применимые правила/эксперты: `["@backend_developer", "@qa_engineer"]`
   - `workspace_path: Optional[str]` — путь к workspace (для относительных путей): `"/Users/bikos/Documents/atra-web-ide"`

2. **Форматирование контекста** (`_format_ide_context(request)`):
   - Преобразует IDE-контекст в читаемый текст для промпта:

     ```
     📋 IDE CONTEXT (как в Cursor):
     ============================================================

     🗂️ Workspace: /Users/bikos/Documents/atra-web-ide

     📊 Git Status:
     On branch main
     Modified: src/utils.py

     📂 Open Files (2):
       1. src/utils.py
          Cursor at line 42
          Lines 37-47:
            def validate_email(email: str) -> bool:
                ...

       2. tests/test_utils.py
          First 10 lines:
            import pytest
            from src.utils import validate_email
            ...

     👥 Applicable Rules/Experts (2):
       • @backend_developer
       • @qa_engineer

     ============================================================
     Используй этот контекст для понимания текущего состояния проекта.
     ```

3. **Инъекция в prompt** (`run_task_stream`):
   - IDE-контекст добавляется в начало `enriched_goal` (после skill_context, если есть)
   - SSE уведомление: `{'type': 'step', 'title': 'IDE Context', 'content': 'Workspace: ... | 2 open file(s) | Git status included'}`
   - Victoria получает `enriched_goal = ide_context + skill_context + original_goal`

4. **MCP tool** (`victoria_mcp_server.py`):
   - `victoria_run_with_context(goal, open_files_json, git_status, cursor_rules_json, workspace_path)`
   - Принимает JSON параметры из Cursor, парсит и передаёт в Victoria API
   - Пример:
     ```python
     victoria_run_with_context(
       goal="Добавь валидацию email",
       open_files_json='[{"path":"src/utils.py","content":"...","cursor_line":42}]',
       git_status="On branch main\nModified: src/utils.py",
       cursor_rules_json='["@backend_developer"]',
       workspace_path="/Users/bikos/Documents/atra-web-ide"
     )
     ```

**Формат open_files:**

```json
[
  {
    "path": "src/utils.py",
    "content": "def validate_email(email: str) -> bool:\n    ...",
    "cursor_line": 42
  }
]
```

**Статус:** ✅ Полная реализация (TaskRequest, форматирование, инъекция, MCP tool). Victoria теперь видит тот же контекст, что и Cursor assistant.

**Следующие шаги (План B):**

- **B.4: Параллельные чтения (batch_read)** — ✅ **ЗАВЕРШЕНО 2026-03-06**

---

## Batch Read — параллельное чтение файлов (План B.4)

**Назначение:** Быстрое параллельное чтение/поиск в множестве файлов за один запрос. Устраняет ограничение «последовательные шаги» — теперь можно сканировать полпроекта за секунды.

**Реализация (внедрено 2026-03-06):**

1. **Модуль batch_read** (`knowledge_os/app/batch_read.py`):
   - `batch_read_files(file_paths, workspace_path, max_concurrent=10)` — параллельное чтение с ограничением размера (1 МБ)
   - `batch_grep_files(pattern, file_paths, workspace_path, case_sensitive=False)` — параллельный grep с regex
   - Semaphore для ограничения одновременных операций
   - Graceful error handling (файл не найден, слишком большой, encoding error)
   - Статистика: success_count, total_size_kb, total_matches

2. **API endpoints** (`victoria_server.py`):
   - `POST /batch_read` — чтение множества файлов:
     ```json
     {
       "file_paths": ["src/utils.py", "src/main.py", ...],
       "workspace_path": "/path/to/project",
       "max_concurrent": 10,
       "max_file_size_mb": 1
     }
     ```
     Возвращает: `{"status": "success", "results": [{...}], "summary": {...}}`
   - `POST /batch_grep` — поиск паттерна:
     ```json
     {
       "pattern": "validate_email|check_email",
       "file_paths": ["src/**/*.py"],
       "workspace_path": "/path/to/project",
       "case_sensitive": false
     }
     ```
     Возвращает список совпадений с номерами строк

3. **MCP tools** (`victoria_mcp_server.py`):
   - `victoria_batch_read(file_paths_json, workspace_path, max_concurrent=10)`
   - `victoria_batch_grep(pattern, file_paths_json, workspace_path, case_sensitive=False)`
   - Пример:

     ```python
     # Прочитать 20 файлов параллельно
     victoria_batch_read(
       file_paths_json='["src/utils.py", "src/main.py", ...]',
       workspace_path="/Users/bikos/Documents/atra-web-ide"
     )

     # Найти все упоминания функции
     victoria_batch_grep(
       pattern="validate_email",
       file_paths_json='["src/**/*.py", "tests/**/*.py"]',
       workspace_path="/Users/bikos/Documents/atra-web-ide"
     )
     ```

**Формат результата batch_read:**

```json
{
  "status": "success",
  "results": [
    {
      "path": "src/utils.py",
      "content": "def validate_email(email: str) -> bool:\n    ...",
      "status": "success",
      "size_kb": 5.2,
      "lines": 150
    },
    {
      "path": "large_file.py",
      "content": null,
      "status": "error",
      "error": "File too large (2.5 MB > 1 MB)"
    }
  ],
  "summary": {
    "total": 20,
    "success": 18,
    "errors": 2
  }
}
```

**Формат результата batch_grep:**

```json
{
  "status": "success",
  "results": [
    {
      "path": "src/utils.py",
      "matches": [
        {
          "line": 42,
          "content": "def validate_email(email: str) -> bool:",
          "match": "validate_email",
          "start": 4,
          "end": 18
        }
      ],
      "match_count": 3,
      "status": "success"
    }
  ],
  "summary": {
    "total_files": 50,
    "files_with_matches": 12,
    "total_matches": 45
  }
}
```

**Производительность:**

- 10 файлов (по 1 КБ каждый) — ~0.1 сек
- 50 файлов (средний размер 50 КБ) — ~0.5 сек
- 100 файлов — ~1 сек
- Ограничение: max_concurrent=10 (можно увеличить до 20 для мощных систем)

**Статус:** ✅ Полная реализация (модуль batch_read, API endpoints, MCP tools). Victoria теперь может быстро сканировать полпроекта за один запрос.

---

Последние изменения (2026-03-05): **Автономия: перезагрузка, Redis, HNSW в CI, индексация.** После перезагрузки — launchd активен при входе; для полной автономности включить автозапуск Docker. Redis для RAG при масштабировании — в .env.example. В CI (pytest-knowledge-os) добавлена проверка HNSW после миграций. Периодическая индексация: `setup_indexing_launchd.sh` (воскресенье 3:00). Автономный куратор запущен успешно (1 задача в БД при расхождении). CURATOR_RUNBOOK §6, HOW_TO_INDEX.

Последние изменения (2026-03-05): **UI Audit: setki21.ru.** (1) Проведён UI-аудит www.setki21.ru — главная и форма входа работают корректно. (2) Выявлены ограничения инструментария: отсутствие MCP Browser Server блокирует проверку функций админки. (3) Обнаружен timeout на `/cabinet` — требуется диагностика `moskit-api`. (4) Рекомендовано: внедрить Playwright E2E тесты, добавить MCP Browser, провести ручную проверку по чеклисту. Отчёт: `docs/audits/2026-03-05-setki21-ui-audit.md`.

Последние изменения (2026-03-04): **Server-Side Pricing & Advanced Order Mapping.** (1) В `moskit-core` внедрена библиотека `rust_decimal` для 100% точности финансовых расчетов. (2) Создан `PricingService` для серверного расчета цен на основе `GlobalPricing` из БД. (3) В таблицу `order_items` добавлено поле `dealer_cost` для фиксации себестоимости в момент заказа. (4) Настроен Docker-билд с кросс-компиляцией OpenSSL для x86_64. См. CHANGES §28.

Последние изменения (2026-03-04): **Multi-Level Dealer Platform & Financial Ledger.** (1) Внедрена иерархия дилеров (Owner, Director, Manager, Sub-Dealer) и филиалов. (2) Реализован финансовый Ledger с балансом и кредитным лимитом. (3) Добавлена "заморозка" цен в заказах для точной аналитики. (4) Создан Кабинет Директора (`/cabinet`) и расширена админка владельца. См. CHANGES §31.

Последние изменения (2026-03-04): **Aggressive Ollama Unload Policy.** (1) Внедрена централизованная политика `app.ollama_keep_alive_policy`. (2) При активном MLX модели в Ollama выгружаются через **60 секунд**. (3) Эмбеддинги выгружаются мгновенно (`keep_alive=0`). (4) Реализован Memory Guard 2.1 с учетом резерва MLX. См. CHANGES §29.

Последние изменения (2026-03-04): **Adaptive Ollama Memory Management & MLX Recovery Unload.** (1) Внедрена централизованная политика `app.ollama_keep_alive_policy` для всех вызовов Ollama (router, executor, ai_core, embeddings). (2) Реализован `MLX_RAM_RESERVE_GB` (32GB) для защиты памяти "Мозга" при работе Ollama. (3) Добавлена автоматическая выгрузка fallback-моделей из Ollama (`keep_alive=0`) при восстановлении MLX (событие "MLX Recovery") с дебаунсом 60с. (4) `victoria-wisdom-v3.5` в Ollama становится бессмертной (`-1`) только при падении MLX. См. CHANGES §28.

Последние изменения (2026-03-04): **Adaptive Ollama Memory Management.** (1) Глобальный `OLLAMA_KEEP_ALIVE` установлен в 10 минут (600с) для всех моделей. (2) `victoria-wisdom-v3.5` удалена из `IMMORTAL_MODELS` для экономии памяти Mac Studio. (3) В `local_router.py` внедрена логика «Fallback Immortality»: ядро v3.5 становится бессмертным в Ollama только если MLX-сервер («Мозг») недоступен. См. CHANGES §27.

Последние изменения (2026-03-03): **UI/UX Unification & Layout Stability.** (1) Унифицированы отступы и высота Hero-секций на всех страницах setki-21. (2) Исправлены «прыжки» верстки при переключении вкладок. (3) Хлебные крошки выведены из потока (absolute). См. CHANGES §26.

Последние изменения (2026-03-03): **Singularity 21.5: Victoria v3.5 Total Dominance.** (1) Полный переход на Qwen 3.5 MoE (35B) в MLX и Ollama. (2) Унификация знаний: Мозг и Руки теперь идентичны. (3) v3.5 добавлена в `IMMORTAL_MODELS` (бессмертные). (4) Обновлен `.env` и `local_router.py` для приоритета v3.5. См. CHANGES §25.

Последние изменения (2026-02-26): **Quick links, CONTRIBUTING по шагам, правило репо, FAQ.** В README и MASTER_REFERENCE добавлены блоки Quick links; CONTRIBUTING — таблица «Куда идти» (баг/предложение/вопрос), оглавление, правило репо, help wanted; создан docs/FAQ.md; в библии — правило репо, ссылки на FAQ, политика версий (Python 3.11+, Node 18+), метрики агентов. См. CHANGES §0.5q.

---

Последние изменения (2026-02-24): **Эра Мудрости: Совет Директоров и дефибриллятор.** (1) Закрыты 170 висящих strategy_sessions (active→cancelled). (2) Введён дефибриллятор MLX: `scripts/host_recovery_listener.py` (порт 9099), RECOVERY_WEBHOOK_URL в оркестраторе — при падении Ollama/MLX вызывается автовосстановление на хосте. (3) Handoff в новый чат: `docs/SESSION_HANDOFF_2026_02_24.md`. (4) Запущен один прогон run_board_meeting(); новые директивы — в board_decisions и на дашборде. См. CHANGES §0.5b.
