# Границы src/ и knowledge_os (дублирование кода)

**Назначение:** явно зафиксировать, какой путь — продакшен для какого домена, чтобы при правках не допускать расхождения логики и двойных правок. Рекомендация из [PROJECT_GAPS_ANALYSIS_2026_02_05.md](PROJECT_GAPS_ANALYSIS_2026_02_05.md) §1 (Backend, Игорь, Роман).

**Обновлено:** 2026-02-05

---

## 1. Краткая сводка

| Путь | Домен | Роль в проекте | Используется в Web IDE / корпорации |
|------|--------|-----------------|-------------------------------------|
| **knowledge_os/app/** | Корпорация (агенты, оркестратор, воркер, эксперты, знания) | Единый источник истины для чата, задач, дашбордов, RAG, Smart Worker | ✅ Да: backend вызывает Knowledge OS API; оркестратор, воркер, дашборды — из knowledge_os |
| **src/agents/bridge/** | Victoria Server, Victoria Telegram Bot | Точка входа POST /run (Victoria), бот для Telegram | ✅ Да: контейнер victoria-agent запускает `python -m src.agents.bridge.victoria_server`; бот — `victoria_telegram_bot` |
| **src/** (остальное) | Алгоритмическая торговля (сигналы, исполнение, фильтры, Telegram-бот для торговли) | Домен atra / торговые стратегии | ❌ Для Web IDE не используется; backend не импортирует из src/ |

---

## 2. knowledge_os/app/ — корпорация (продакшен для чата/задач)

- **Содержимое:** оркестратор (enhanced_orchestrator, streaming_processor), REST API (rest_api.py), Smart Worker (smart_worker_autonomous.py), Victoria Enhanced (victoria_enhanced.py), делегирование (task_delegation, victoria_enhanced), эксперты (expert_services), знания (knowledge_nodes, semantic_cache), дашборды (corporation-dashboard), Nightly Learner, Совет Директоров (strategic_board), json_fast, http_client, db_pool и др.
- **Запуск:** knowledge_os/docker-compose.yml (knowledge_rest, knowledge_os_worker, corporation-dashboard, enhanced_orchestrator и т.д.).
- **Для Web IDE:** backend (8080) обращается к Knowledge OS REST API (8002), к Victoria (8010). Чат, план, задачи, эксперты, RAG — поток идёт через knowledge_os (API и Victoria). Источник истины по задачам, экспертам, знаниям — БД knowledge_os (PostgreSQL).

---

## 3. src/agents/bridge/ — Victoria Server и Victoria Telegram Bot (продакшен)

- **Содержимое:** `victoria_server.py` (FastAPI POST /run, контракт TaskRequest/TaskResponse, understand_goal, plan, executor, вызовы Veronica и knowledge_os), `victoria_telegram_bot.py` (бот для чата с Victoria из Telegram).
- **Запуск:** контейнер **victoria-agent** в knowledge_os/docker-compose.yml: `command: python -m src.agents.bridge.victoria_server`. Telegram-бот — отдельный процесс на хосте (не в Docker): `python3 -m src.agents.bridge.victoria_telegram_bot`.
- **Для Web IDE:** точка входа Victoria (8010) — именно victoria_server; контракт (goal, project_context) и все вызовы к оркестратору/Veronica/БД идут из этого модуля. При изменениях в чате или контракте Victoria — сверять с [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) §5 (изменения в чате, контракт Victoria).

---

## 4. src/ (остальное) — домен алгоритмической торговли

- **Содержимое:** telegram (bot, handlers, bot_core — торговый бот), signals (signal_live, simple_processor), execution (auto_execution, position_manager, fee_manager), filters (interest_zone и др.), config (smart_hybrid и др.), data (optimized_strategy и др.), utils, domain, database, risk, strategies и т.д.
- **Роль:** код для проекта atra / алгоритмическая торговля (интрадей, крипторынок). В контексте **atra-web-ide** (Web IDE, корпорация Singularity 9.0) эти модули **не используются**: backend не импортирует из src/; чат и задачи идут через Victoria и knowledge_os.
- **Риск расхождения:** при наличии похожей логики в knowledge_os (например, если когда-то копировали telegram или utils) правки в одном месте не попадают в другое. **Рекомендация:** при правках в src/ (telegram, signals, execution, filters, config, data, utils) проверять, нет ли аналога в knowledge_os/app или в src/agents/bridge; при добавлении новой общей логики — по возможности выносить в единый модуль (knowledge_os или общий пакет) и ссылаться из обоих мест, либо явно задокументировать «только для торгового домена».

---

## 5. Что делать при изменениях

- **Правки в knowledge_os/app/** — основной контур корпорации; тесты (test_rest_api, test_victoria_chat_and_request, test_json_fast_http_client) и чеклист §1/§5 [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) по затронутой области.
- **Правки в src/agents/bridge/** — контракт Victoria (goal, project_context), делегирование, RAG; сверять с чеклистом §5 (изменения в чате, Victoria) и с knowledge_os (victoria_enhanced, task_delegation).
- **Правки в src/ (telegram, signals, execution, filters, config, data, utils)** — домен торговли; при появлении дублирования с knowledge_os — зафиксировать в этом документе или вынести общую часть в единый источник истины.

---

*Документ создан по рекомендации PROJECT_GAPS_ANALYSIS §1. При обновлении границ или переносе кода — обновить этот файл и MASTER_REFERENCE §1г.*
