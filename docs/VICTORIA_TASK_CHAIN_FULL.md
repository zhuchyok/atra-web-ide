# Полная цепочка: от поручения задачи Victoria до ответа

**Цель:** зафиксировать, как задача попадает в Victoria, кто и как её распределяет, кто исполняет (один эксперт или команда), как результат возвращается. Чтобы система была правильной и быстрой — нужна ясность на каждом шаге.

**Дата:** 2026-02-11

---

## 1. Схема цепочки (высший уровень)

**Единая логика «логика мысли» (план одноимённый):** стратегия → память → план → выполнение → рефлексия (чекпоинты) → ответ с confidence.

```
Пользователь (чат / API)
        │
        ▼
   POST /run (goal, project_context, session_id)
        │
        ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │ VICTORIA (victoria_server.py)                                    │
   │ 0. [Стратегия] _select_strategy → quick/deep/clarify/decline + confidence │
   │    → при need_clarification: вопросы, выход; при decline: отказ, выход     │
   │ 1. [Память] Контекст: session + долгосрочная память (long_term_memory)   │
   │ 2. Понимание цели, уточняющие вопросы (если нужно)               │
   │ 3. Опционально: оркестратор (IntegrationBridge) → план/назначения│
   │ 4. Маршрутизация: кто исполняет?                                 │
   └─────────────────────────────────────────────────────────────────┘
        │
        ├──► [Veronica]     — одношаговые запросы (покажи файлы, список) → один агент
        │
        ├──► [Victoria Enhanced] — сложные/исполнение/код/анализ
        │         │ [Рефлексия] При методе recap: чекпоинты при провале шага → replan при необходимости
        │         ├── Department Heads (аналитика) → отдел → эксперты отдела / swarm
        │         ├── Task Delegator → делегирование в MultiAgentCollaboration → один назначенный агент
        │         └── Метод по категории:
        │             • simple / react — одна модель (или ReAct + инструменты)
        │             • swarm — много экспертов параллельно (до 16 из БД)
        │             • consensus — до 10 экспертов, консенсус
        │             • extended_thinking, tree_of_thoughts, recap — одна модель, углублённо
        │
        └──► [agent_run]    — быстрый путь (simple_chat) или fallback — одна модель Victoria
        │
        ▼
   Ответ (TaskResponse: status, output, knowledge: strategy, confidence, uncertainty_reason, execution_trace)
   После успеха: сохранение в session_context и long_term_memory (если включено)
        │
        ▼
   Пользователь
```

---

## 2. Кто распределяет задачу

| Этап | Где | Что делает |
|------|-----|------------|
| **Тип задачи** | `task_detector.detect_task_type()` | Определяет: `simple_chat`, `veronica`, `department_heads`, `enhanced`. Ключевые слова + PREFER_EXPERTS_FIRST. |
| **План/назначения** | `IntegrationBridge.process_task()` (если ORCHESTRATION_V2_ENABLED) | V2: EnhancedOrchestratorV2.run_phases_1_to_5 → план, assignments, strategy, execution_order. Existing: ExpertMatchingEngine.find_best_expert_for_task → **один** эксперт в `assignments["main"]`. Результат — **только план**, не исполнение. |
| **Использование плана в Victoria** | `_build_orchestration_context(orchestration_plan)` | Текст стратегии и назначений подставляется в контекст (промпт) для Enhanced и для agent.run. **Важно:** оркестратор не вызывает исполнение в БД (tasks/smart_worker) — это другой, асинхронный контур. |

При **EXECUTE_ASSIGNMENTS_IN_RUN=true** (по умолчанию в docker-compose): после получения assignments вызывается **execute_assignments_async** → по каждому эксперту из плана вызывается **run_smart_agent_async**; результаты подставляются в контекст Victoria вместо текста плана. См. п.12.2 плана «как я», [execute_assignments.py](knowledge_os/app/execute_assignments.py).

Итого: **распределение** — это выбор маршрута (Veronica / Enhanced / agent_run) и при Enhanced — выбор **метода** (simple, react, swarm, consensus, …). Назначения из IntegrationBridge идут в подсказку модели (или при EXECUTE_ASSIGNMENTS_IN_RUN — в реальные вызовы экспертов через run_smart_agent_async).

### 2.1 Откуда вызываются эксперты при Victoria в Docker

| Где что выполняется | Описание |
|---------------------|----------|
| **Запрос в Victoria** | Backend (или чат) шлёт POST /run на **victoria-agent:8010** (с хоста — localhost:8010). Обработчик — процесс внутри контейнера victoria-agent. |
| **IntegrationBridge, execute_assignments** | Выполняются **внутри того же контейнера** victoria-agent (Python-процесс Victoria). План и вызовы экспертов — в одном процессе. |
| **run_smart_agent_async (ai_core)** | Тоже внутри контейнера. Отправляет HTTP-запросы к LLM по адресу из env: **OLLAMA_BASE_URL** (в docker-compose задан `http://host.docker.internal:11434`). |
| **Инференс LLM** | **На хосте**: Ollama слушает 11434, MLX при необходимости — 11435. Контейнер обращается к ним через `host.docker.internal`, т.е. эксперты «вызываются» логикой из контейнера, а тяжёлая работа (модель) — на машине хоста. |

Итого: **эксперты вызываются из контейнера victoria-agent** (код execute_assignments → ai_core.run_smart_agent_async); запросы к моделям уходят на **хост** (Ollama/MLX по host.docker.internal).

---

## 3. Кто исполняет (один эксперт или команда)

| Маршрут | Кто исполняет | Один или команда |
|---------|----------------|-------------------|
| **Veronica** | Veronica Agent (POST к ней, она вызывает свою LLM + инструменты) | **Один** агент (Вероника). |
| **Enhanced → Department Heads** | Отдел (head + эксперты отдела), при стратегии swarm — несколько экспертов отдела | **Команда** отдела или один head. |
| **Enhanced → Task Delegator** | MultiAgentCollaboration.execute_task(task) — один назначенный агент по задаче | **Один** назначенный агент. |
| **Enhanced → simple** | Один вызов LLM (Виктория, выбранная модель по категории) | **Один** (модель). |
| **Enhanced → react** | ReActAgent — одна модель + инструменты (файлы, терминал) | **Один** (модель + инструменты). |
| **Enhanced → swarm** | SwarmIntelligence.solve — параллельные ответы от нескольких «экспертов» (имена из get_all_expert_names, до 16) | **Команда** (много вызовов LLM с разными expert_name). |
| **Enhanced → consensus** | ConsensusAgent.reach_consensus — до 10 экспертов (имена из БД или fallback список) | **Команда** (несколько экспертов, затем консенсус). |
| **Enhanced → extended_thinking / tree_of_thoughts / recap** | Одна модель, углублённое рассуждение | **Один** (модель). |
| **agent_run** | Victoria base agent (OllamaExecutor + инструменты) | **Один** (Victoria как исполнитель). |

**Когда «вся команда» (много экспертов):** только при методе **swarm** или **consensus** внутри Victoria Enhanced, либо при **Department Heads** со стратегией swarm. Остальные пути — один исполнитель (модель или Veronica).

---

## 4. Как выбирается метод в Enhanced (категория → метод)

`VictoriaEnhanced._categorize_task(goal)` даёт категорию. `_select_optimal_method(category, goal)` выбирает метод:

| Категория | Метод по умолчанию | Команда? |
|-----------|--------------------|----------|
| informational | simple | Нет |
| status_query | simple | Нет |
| fast | react / simple | Нет |
| reasoning | extended_thinking / recap | Нет |
| planning | tree_of_thoughts / hierarchical | Нет (или hierarchical — несколько ролей) |
| **complex** | **swarm** / consensus | **Да** (много экспертов) |
| execution | react / simple | Нет |
| coding | react / simple | Нет |
| general | react / simple | Нет |

«Сложная» задача (complex) — та, где в цели есть слова про команду/экспертов/критичность или аналитику кода; тогда действительно вызывается swarm или consensus.

---

## 5. Как результат возвращается к Victoria и пользователю

- **Синхронно в процессе одного запроса:** Victoria вызывает либо `delegate_to_veronica()`, либо `enhanced.solve()`, либо `agent.run()`. Все они возвращают результат в память (dict или str). Victoria упаковывает это в **TaskResponse** (output, knowledge с execution_trace, correlation_id) и отдаёт клиенту.
- **Асинхронный режим (async_mode=true):** то же самое, но выполнение идёт в фоне (`_run_task_background`), клиент получает 202 и опрашивает GET /run/status/{task_id}, пока в store не появится status=completed/failed и output.
- Отдельный контур **tasks в БД + smart_worker** (очередь задач Knowledge OS) в этой цепочке **не участвует** — он для фонового обучения и батч-задач, не для ответа на один POST /run.

Итого: **возврат** — всегда через возвращаемое значение вызова (Veronica/Enhanced/agent_run) → TaskResponse → пользователь. Нет отдельного «сбора ответов от экспертов в БД» в рамках этого запроса.

### 5.1 Контракт расширенного ответа (логика мысли)

При внедрении плана «Логика мысли» (см. [PLAN_REASONING_LOGIC_VICTORIA.md](PLAN_REASONING_LOGIC_VICTORIA.md)) ответ Victoria расширяется опциональными полями. Обратная совместимость: старые клиенты их игнорируют.

| Поле | Тип | Обязательность | Описание |
|------|-----|----------------|----------|
| `status` | string | да | Без изменений: `success`, `needs_clarification`, `error` и т.д. |
| `output` | any | да | Без изменений. |
| `knowledge` | object | опционально | Расширяется вложенными полями ниже. |
| `knowledge.strategy` | string | нет (новое) | `quick_answer` \| `deep_analysis` \| `need_clarification` \| `decline_or_redirect`. |
| `knowledge.strategy_reason` | string | нет (новое) | Краткая причина выбора стратегии. |
| `knowledge.confidence` | float | нет (новое) | 0.0–1.0. |
| `knowledge.uncertainty_reason` | string | нет (новое) | Текст, если уверенность низкая. |

### 5.2 Память: сессия и долгосрочная (Фаза 2 плана «Логика мысли»)

- **Сессия:** при `session_id` Victoria подмешивает контекст из `session_context` (get_session_context) и краткую память по задаче (get_session_memory_summary → блок «Ранее по этой задаче (сессия)»). После успешного ответа вызывается _save_session_exchange(goal, output).
- **Долгосрочная память:** при `LONG_TERM_MEMORY_ENABLED=true` используется таблица `long_term_memory` (ключ user_key=session_id или "anonymous", project_context). После каждого успешного ответа сохраняется краткое резюме (goal_summary, outcome_summary до 500 символов); при новом запросе до K последних «нитей» подмешиваются в блок «Ранее по этому проекту/пользователю» в промпте Enhanced. Сессия и долгосрочная память объединяются в одном контексте (task_memory + long_term_memory). См. knowledge_os/app/long_term_memory.py, миграция add_long_term_memory.sql.

### 5.3 Рефлексия и пересмотр плана (Фаза 3, ReCAP)

При методе **recap** в Victoria Enhanced после каждого low-level шага проверяется результат. Если шаг провален или пуст (`_is_step_failed_or_empty`) и включена рефлексия (`VICTORIA_REFLECTION_ENABLED`), вызывается `_should_revise_plan` (один короткий вызов LLM): «пересмотреть план? ДА/НЕТ + причина». При «ДА» и не исчерпанном лимите пересмотров (`VICTORIA_MAX_PLAN_REVISIONS`, по умолчанию 1) контекст дополняется `previous_plan_failure` (шаг, причина), план пересобирается через `_decompose_goal` с учётом предыдущей попытки, выполнение продолжается с нового плана. Реализация: `knowledge_os/app/recap_framework.py`.

---

## 6. Выявленные разрывы и неточности

1. **План оркестратора не ведёт к явному исполнению.** IntegrationBridge (V2 или ExpertMatchingEngine) возвращает assignments и strategy, но Victoria только подставляет их в текст контекста. Реального «поставить задачу эксперту X в БД и дождаться результата» в рамках POST /run нет. Исполнение делают сама Victoria (simple/react/swarm/consensus) или Veronica.
2. **Кто «вся команда».** Команда задействована только при swarm/consensus или Department Heads swarm. Во всех остальных случаях исполняет один исполнитель (модель или Veronica). Это по дизайну, но должно быть явно зафиксировано (здесь и в runbook).
3. **Дублирование ролей.** При task_type=veronica задача уходит в Veronica целиком (она сама планирует и выполняет). По VERONICA_REAL_ROLE правильно: только одношаговые запросы (покажи файлы, список) → Veronica; «сделай/напиши код» → Enhanced (эксперты/модель). При PREFER_EXPERTS_FIRST=true так и работает; при false — исполнительные запросы тоже могут уйти в Veronica (риск перегрузки «руками»).
4. **Скорость.** Быстрые пути: simple_chat (без Enhanced), informational (simple без ReAct), делегирование в Veronica для «покажи файлы». Медленные: swarm, consensus, extended_thinking, Department Heads. Для «правильной и быстрой» системы важно не направлять простые запросы в тяжёлые методы.

---

## 7. Рекомендации: правильность и скорость

**Правильность**

- Явно считать источником истины: **Veronica — только одношаговые действия** (см. VERONICA_REAL_ROLE, task_detector, PREFER_EXPERTS_FIRST). Не слать ей целые задачи «напиши сервис» / «исправь все баги».
- Использовать **orchestration_context** (план и назначения от IntegrationBridge) осознанно: либо только как подсказку для LLM, либо в перспективе — реально вызывать исполнение по назначениям (например, вызов run_smart_agent_async по списку экспертов из assignments и сбор ответов). Сейчас это не делается — зафиксировать в коде/доках.
- Для сложных задач (complex) оставить swarm/consensus как «команда экспертов»; для execution/coding — react/simple. Не помечать простые запросы как complex.

**Скорость**

- Не вызывать Enhanced для simple_chat (уже так: should_use_enhanced возвращает false для simple_chat).
- Для «что умеешь» / «кто ты» — быстрый путь в Victoria (capabilities из configs) без LLM (уже есть).
- При включённом оркестраторе (V2): учитывать, что run_phases_1_to_5 может добавлять задержку; при необходимости делать вызов оркестратора опциональным по флагу или типу задачи.
- Сложные методы (swarm, consensus) оставлять только для категории complex; не повышать категорию без веских причин.

**Документация и код**

- В MASTER_REFERENCE или в отдельном runbook добавить ссылку на этот документ (полная цепочка).
- В коде (victoria_server, victoria_enhanced) в ключевых местах маршрутизации оставить короткие комментарии: «Orchestrator plan only as context, not execution dispatch» и «Team = swarm/consensus or dept swarm only».

---

## 8. Связь с существующими документами

- **VERONICA_REAL_ROLE.md** — роль Вероники («руки»), не слать ей целые задачи.
- **VERIFICATION_CHECKLIST_OPTIMIZATIONS.md** — при изменениях маршрутизации проверять цепочку и тесты.
- **CHANGES_FROM_OTHER_CHATS.md** — при внедрении изменений в цепочку добавлять запись сюда и сюда (VICTORIA_TASK_CHAIN_FULL).
- **NEXT_STEPS_CORPORATION.md** — при доработке «исполнение по назначениям оркестратора» описать там.

---

## 9. Проверка логики и связей (тесты)

- **Логика мысли (Фаза 5):** `knowledge_os/tests/test_reasoning_logic_recap.py` — ReCAP: _is_step_failed_or_empty, _build_high_level_prompt с previous_plan_failure, _execute_plan возвращает (results, should_replan, failure_info). `backend/app/tests/test_reasoning_logic_contract.py` — контракт ответа Victoria: needs_clarification → clarification_questions; knowledge.strategy, confidence в raw.
- **Маршрутизация (task_detector):** `backend/app/tests/test_task_detector_chain.py` — тесты `detect_task_type` (simple_chat, veronica, enhanced, department_heads) и `should_use_enhanced` при PREFER_EXPERTS_FIRST. Скрипт `scripts/test_task_detector.py` — те же кейсы для быстрой проверки.
- **План оркестратора:** в том же файле класс `TestOrchestrationContext` — тесты `_build_orchestration_context` (пустой ввод, strategy, assignments) и `_orchestrator_recommends_veronica` (True при expert_name Veronica/Вероника).
- **Делегирование Veronica:** `backend/app/tests/test_veronica_delegate.py` — delegate_to_veronica (пустой goal → None, 200 → dict, ошибки/не-dict → None), mock aiohttp.
- **Оркестратор и эксперты:** `knowledge_os/tests/test_integration_bridge.py` (IntegrationBridge.process_task, use_v2=False); `knowledge_os/tests/test_expert_services.py` (get_all_expert_names, get_expert_services_text, list_experts_by_role).
- **Один прогон всей системы:** см. [TESTING_FULL_SYSTEM.md](TESTING_FULL_SYSTEM.md). Команда: `./scripts/run_all_system_tests.sh` (backend 57 + knowledge_os 41 unit); при `RUN_INTEGRATION=1` — интеграционные тесты.
- **Запуск по отдельности:** `pytest backend/app/tests/test_task_detector_chain.py -v`; полный backend: `pytest backend/app/tests/ -q`.

При изменении маршрутизации или формата плана оркестратора — обновлять тесты и этот документ.

---

*Документ подготовлен по результатам анализа кода: victoria_server.py, task_detector.py, enhanced_router.py, victoria_enhanced.py, task_orchestration/integration_bridge.py.*
