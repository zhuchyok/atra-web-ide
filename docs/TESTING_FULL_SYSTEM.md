# Тестирование всей системы: Victoria, Veronica, оркестраторы, эксперты

**Цель:** тестировать не только Victoria, но и Veronica, оркестраторов и экспертов — как всё работает вместе, чтобы система была предсказуемой и воспроизводимой («копия тебя»).

**Обновлено:** 2026-02-08

---

## 1. Что тестируем

| Компонент | Что проверяем | Где тесты | Требует живых сервисов |
|-----------|----------------|-----------|-------------------------|
| **Victoria** | Маршрутизация (task_detector), цепочка (orchestration context), API (POST /run) | backend/app/tests/test_task_detector_chain.py, test_plan_cache, test_strategic_classifier; knowledge_os/tests/test_victoria_chat_and_request.py | Часть — unit; live_chain — да (Victoria 8010) |
| **Veronica** | Делегирование (delegate_to_veronica: формат, таймаут, ошибки), цепочка Victoria→Veronica→ответ | backend/app/tests/test_veronica_delegate.py; scripts/test_full_chain_veronica.py | Unit с mock; полная цепочка — да (Victoria + Veronica) |
| **Оркестраторы** | IntegrationBridge (план, assignments), V2/Existing, рекомендация Veronica | backend/app/tests/test_task_detector_chain.py (TestOrchestrationContext); knowledge_os/tests/test_integration_bridge.py | Unit без БД; V2 run_phases — опционально БД |
| **Эксперты** | Список имён (swarm/consensus), услуги для промптов, Department Heads | knowledge_os/tests/test_expert_services.py; test_chain_department_heads.py; test_victoria_chat_and_request (department fallback) | get_all_expert_names — employees.json без БД; с БД — полный список |

---

## 2. Как запускать тесты

### Быстрый прогон (без живых сервисов)

```bash
# Backend: маршрутизация, цепочка, делегирование Veronica (mock), стратегический классификатор, план-кэш, RAG, метрики
# Запускать из корня репо (тесты с импортом src.agents.bridge добавляют корень в path через parents[3])
pytest backend/app/tests/ -q

# Knowledge OS: Victoria Enhanced (casual chat, department, PREFER_EXPERTS_FIRST), expert_services, IntegrationBridge, department_heads, json_fast, rest_api (нужна БД или mock), skills
cd knowledge_os && python3 -m pytest tests/ -q -m "not integration and not slow"
# Или из корня репо:
PYTHONPATH=.:knowledge_os pytest knowledge_os/tests/ -q -m "not integration and not slow"
```

### Полный прогон (включая интеграционные)

```bash
# 1. Запустить сервисы (Victoria, Veronica, БД, Redis — по необходимости)
docker compose -f knowledge_os/docker-compose.yml up -d

# 2. Backend
pytest backend/app/tests/ -v

# 3. Knowledge OS (все тесты, в т.ч. integration)
cd knowledge_os && python3 -m pytest tests/ -v

# 4. Полная цепочка Victoria → Veronica (скрипт)
VICTORIA_URL=http://localhost:8010 VERONICA_URL=http://localhost:8011 python3 knowledge_os/scripts/test_full_chain_veronica.py
# Или быстрый тест без долгой задачи:
GOAL="Привет" python3 knowledge_os/scripts/test_full_chain_veronica.py
```

### Один скрипт «всё тестировать»

```bash
./scripts/run_all_system_tests.sh
```

Скрипт по умолчанию запускает только быстрый прогон (98 тестов без живых сервисов). **Остальные** запускаются так:

| Что | Как запустить | Что нужно |
|-----|----------------|-----------|
| **Интеграционные** (live Victoria, POST /run) | `RUN_INTEGRATION=1 ./scripts/run_all_system_tests.sh` | Victoria на 8010, опционально Veronica/БД |
| **С БД/Redis** (e2e, knowledge_graph, load, performance_optimizer, file_watcher, rest_api, service_monitor) | `RUN_WITH_DB=1 ./scripts/run_all_system_tests.sh` | PostgreSQL (knowledge_os), Redis; могут падать без поднятой инфры |

Одной командой «всё включая их»: `RUN_INTEGRATION=1 RUN_WITH_DB=1 ./scripts/run_all_system_tests.sh` (предварительно поднять `docker compose -f knowledge_os/docker-compose.yml up -d`).

### E2E (Playwright): чат и health

После поднятия frontend (3000), backend (8080) и при необходимости Victoria (8010):

```bash
cd frontend && npm run e2e
```

Переменные: `BASE_URL=http://localhost:3000`, `BACKEND_URL=http://localhost:8080`. Тесты: загрузка страницы чата, отправка сообщения и ожидание ответа; GET /health backend. Конфиг: `frontend/tests/e2e/playwright.config.cjs`. См. CONTRIBUTING.md §2.

**E2E сценарий: стратегический вопрос → board → Victoria**

Проверка цепочки: пользователь задаёт стратегический вопрос → backend вызывает Совет (board/consult) → ответ Victoria содержит рекомендации/риски. Запуск (backend и Victoria должны быть подняты):

```bash
./scripts/test_strategic_chat_e2e.sh
```

Скрипт отправляет в POST /api/chat/stream цель, считающуюся стратегической (например «Какие риски для компании в 2026 году?»), и проверяет, что ответ приходит (статус 200, непустой поток). Опционально можно проверять наличие в SSE полей, связанных с Советом (directive, risk_level). Подробнее: логика стратегических вопросов — backend `is_strategic_question`, вызов board/consult; тесты — `test_strategic_classifier.py`.

**Примечание:** без поднятых PostgreSQL и Redis часть тестов в блоке RUN_WITH_DB=1 падает. Чтобы **все тесты выполнялись без skip** (в т.ч. knowledge_graph, test_load_create_many_links, test_e2e_knowledge_creation_and_linking), нужна БД, где **knowledge_nodes.id имеет тип UUID**: (1) **Либо** поднять БД с нуля по **knowledge_os/db/init.sql** (там уже id UUID) — так делает CI и рекомендуемый локальный прогон. (2) **Либо** привести существующую БД к UUID: применить миграцию **knowledge_os/db/migrations/knowledge_nodes_id_integer_to_uuid.sql** (один раз: `psql $DATABASE_URL -f knowledge_os/db/migrations/knowledge_nodes_id_integer_to_uuid.sql` или через `apply_migrations.py`). Пока в БД `knowledge_nodes.id` — integer (например из бэкапа), эти 4 теста корректно помечаются как skipped. См. VERIFICATION_CHECKLIST_OPTIMIZATIONS §3, EXPERT_CONNECTION_ARCHITECTURE (про экспертов в Docker).

**Рекомендация (эксперты и мировые практики):**
- **Единый источник истины схемы:** канон — **init.sql** (там `knowledge_nodes.id` = UUID). Любая БД с integer — устаревшее состояние; цель — привести всё к канону.
- **Вариант A (БД с нуля от init.sql)** — правильный по умолчанию для **новых окружений**: CI, новый dev, staging, **Docker**. В **Docker** при первом запуске (`docker-compose -f knowledge_os/docker-compose.yml up -d`) Postgres сам выполняет `db/init.sql` из `docker-entrypoint-initdb.d` (пустой volume → каноническая схема). Дальше сервисы при старте или вручную вызывают `apply_migrations.py` — миграции достраивают таблицы; миграция `fix_expert_discussions` условная (UUID или integer по типу `knowledge_nodes.id`), не падает ни на свежей, ни на старой БД.
- **Вариант B (миграция integer→UUID)** — для **уже существующих** инсталляций с данными: прод, бэкап, копия с integer. Миграция идемпотентна (при уже UUID — no-op).
- **Итог:** новый окружение (в т.ч. Docker с нуля) — автоматически канон (A). Существующая БД с integer — один раз миграция (B).

---

## 3. Где какие тесты

| Файл | Компонент | Описание |
|------|-----------|----------|
| backend/app/tests/test_task_detector_chain.py | Victoria, оркестратор | detect_task_type, should_use_enhanced, _build_orchestration_context, _orchestrator_recommends_veronica |
| backend/app/tests/test_veronica_delegate.py | Veronica | delegate_to_veronica: пустой goal → None, ошибка/таймаут → None, 200 → dict с status/output/knowledge |
| backend/app/tests/test_strategic_classifier.py | Чат → Совет | is_strategic_question, get_risk_level |
| knowledge_os/tests/test_victoria_chat_and_request.py | Victoria Enhanced | _is_casual_chat, department fallback, _is_simple_veronica_request, _should_delegate_task (PREFER_EXPERTS_FIRST) |
| knowledge_os/tests/test_expert_services.py | Эксперты | get_all_expert_names (список), get_expert_services_text (строка для промпта) |
| knowledge_os/tests/test_integration_bridge.py | Оркестратор | IntegrationBridge.process_task(use_v2=False) — формат ответа, ключи orchestrator/assignments |
| knowledge_os/tests/test_chain_department_heads.py | Department Heads | determine_department, отделы по ключевым словам |
| knowledge_os/tests/test_live_chain.py | Вся цепочка (live) | Victoria /health, POST /run sync (требует Victoria 8010); **RUN_INTEGRATION=1** |
| knowledge_os/tests/test_e2e.py | E2E | Создание/связи знаний, контекстное обучение; **RUN_WITH_DB=1** |
| knowledge_os/tests/test_knowledge_graph.py | Граф знаний | create_link, get_related_nodes; **RUN_WITH_DB=1** |
| knowledge_os/tests/test_load.py | Нагрузка | Много связей, кэш; **RUN_WITH_DB=1** |
| knowledge_os/tests/test_performance_optimizer.py | Кэш/производительность | query_cache, invalidation; **RUN_WITH_DB=1** (Redis) |
| knowledge_os/tests/test_file_watcher.py | File Watcher | События создания файлов, EventBus; **RUN_WITH_DB=1** |
| knowledge_os/tests/test_rest_api.py | REST API | health, shutdown, защищённые endpoint; **RUN_WITH_DB=1** (БД) |
| knowledge_os/tests/test_service_monitor.py | Service Monitor | Сервисы, is_running; **RUN_WITH_DB=1** |

---

## 4. Связь с документацией

- **VICTORIA_TASK_CHAIN_FULL.md** — кто распределяет, кто исполняет, один или команда; §9 — проверка логики (тесты).
- **VERONICA_REAL_ROLE.md** — Veronica только «руки»; PREFER_EXPERTS_FIRST в task_detector и victoria_enhanced.
- **VERIFICATION_CHECKLIST_OPTIMIZATIONS.md** — при изменениях в маршрутизации/цепочке гонять test_task_detector_chain и обновлять документы.

После добавления или изменения тестов — обновить этот документ (таблицы §1 и §3).
