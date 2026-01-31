# Victoria: полный процесс от запроса до выполнения задачи

Подробное описание: **что**, **кому**, **как** и **где** происходит с момента, когда ты просишь Victoria что-то сделать, до получения результата.

---

## Victoria Agent на порту 8010 — один сервис, три уровня

В чате корпорации и команде добавили **victoria-agent** на порту **8010**. **Victoria Agent / Enhanced / Initiative** — это **один сервис** (один процесс, один контейнер), просто с разным уровнем возможностей. Для полноценной работы Виктории **все три уровня должны быть запущены**.

| Уровень | Что даёт | Как включается |
|--------|----------|-----------------|
| **Victoria Agent** | Базовый: чат с LLM, ответы на запросы, планирование, инструменты (read_file, web_search и т.д.). | Всегда активен в этом процессе. |
| **Victoria Enhanced** | ReAct, Extended Thinking, Swarm, Consensus, Department Heads, делегирование Veronica, выбор модели из Ollama/MLX. | `USE_VICTORIA_ENHANCED=true` (в docker-compose уже true). |
| **Victoria Initiative** | Проактивность: Event Bus, File Watcher, Service Monitor, Deadline Tracker, Skill Registry, автоперезапуск MLX при падении. | `ENABLE_EVENT_MONITORING=true` (в docker-compose уже true). |

**Где это сделано:**
- **Сервер:** `src/agents/bridge/victoria_server.py` — в `lifespan` при старте: если оба флага true, создаётся `VictoriaEnhanced()` и вызывается `await victoria_enhanced_instance.start()`, что поднимает Event Bus, File Watcher, Service Monitor и т.д. (Initiative).
- **Контейнер:** `knowledge_os/docker-compose.yml` — сервис `victoria-agent`, порт `8010:8000`, переменные `USE_VICTORIA_ENHANCED: "true"`, `ENABLE_EVENT_MONITORING: true`.
- **Проверка:** `GET http://localhost:8010/status` — в ответе есть `victoria_levels`: `agent`, `enhanced`, `initiative` (все true при корректном запуске).

---

## 1. Ты отправляешь запрос

**Где:** Чат (терминал `victoria_chat.py` или Web IDE / API).

**Что происходит:**
- Твой текст уходит как `goal` в запросе.
- Вместе с ним могут передаваться: `project_context` (atra-web-ide / atra), `session_id`, `chat_history` (последние 30 пар сообщений).

**Куда идёт запрос:**
- **URL:** `http://localhost:8010/run` (или удалённый Victoria).
- **Метод:** `POST /run`.
- **Режим:** по умолчанию с `async_mode=1` — сервер сразу отвечает 202 и выполняет задачу в фоне; чат опрашивает статус и по завершении показывает результат.

---

## 2. Сервер Victoria принимает запрос

**Где:** `src/agents/bridge/victoria_server.py` — обработчик `run_task`.

**Что происходит по шагам:**

### Пайплайн стандартного VictoriaAgent (мировая практика)

Перед планированием и выполнением Victoria **сначала понимает и переформулирует** запрос под модули:

1. **Understand (понять и переформулировать)** — `understand_goal(raw_goal)`  
   Один быстрый вызов LLM (planner): из сырого запроса пользователя получаем:
   - **restated** — одно ясное предложение: что сделать (понятно исполнителю и инструментам);
   - **category** — `simple` | `investigate` | `multi_step`;
   - **first_step** — рекомендация первого шага (например: «list_directory в frontend»).  
   Так запрос «ошибки на странице X, найди и исправь» превращается в «Проверить структуру frontend и найти причину 404 на странице X» с подсказкой первого шага.

2. **Plan (планирование)** — вызывается уже по **переформулированной** цели (`restated`), не по сырому тексту. План строится короткий (1–2 шага), без галлюцинаций.

3. **Execute (выполнение)** — исполнитель получает задачу в виде «ПЛАН + ПРИСТУПАЙ К ВЫПОЛНЕНИЮ: {restated}» и при необходимости подсказку «Первый шаг: {first_step}». Инструменты только: finish, read_file, list_directory, run_terminal_cmd, ssh_run.

Итог: запрос сначала обдумывается и переводится в форму, удобную для модулей, затем строится план и только потом выполняется.

**Модель:** Victoria использует **и MLX, и Ollama** модели. Сканирует актуальный список при первом запросе (кэш ~2 мин), выбирает **самую мощную доступную** из объединённого списка (приоритет: command-r-plus:104b → deepseek-r1-distill-llama:70b → llama3.3:70b → qwen2.5-coder:32b → …). Роутер (LocalAIRouter) перебирает узлы MLX и Ollama с этой моделью — отвечает тот узел, где она есть. Явно задать модель: `VICTORIA_MODEL=имя_модели`.

1. **Контекст проекта**
   - Берётся `project_context` из запроса или `MAIN_PROJECT` (по умолчанию atra-web-ide).
   - Проверка по whitelist (`ALLOWED_PROJECTS`); при необходимости подставляется безопасный контекст.
   - Формируется `project_prompt` — текст с названием проекта, workspace, правилами про базу знаний (без пользовательского ввода в промпт).

2. **Режим выполнения**
   - **Если `async_mode=1`:** создаётся `task_id`, в памяти сохраняется запись задачи (`status: queued`), в фоне запускается `_run_task_background(...)`, клиенту возвращается **202** и `task_id` / `status_url`. Дальше шаги 3–7 идут уже в фоновой задаче.
   - **Если без async:** те же шаги выполняются в том же запросе, ответ — один раз с готовым результатом.

3. **Выбор движка**
   - Если `USE_VICTORIA_ENHANCED=true` — используется **Victoria Enhanced** (`knowledge_os/app/victoria_enhanced.py`).
   - Иначе — стандартный **VictoriaAgent** (Ollama/планирование и т.д.).

Дальше описан путь через **Victoria Enhanced** (основной сценарий).

---

## 3. Victoria Enhanced: вход в solve()

**Где:** `knowledge_os/app/victoria_enhanced.py` — метод `solve(goal, use_enhancements=True, context=...)`.

**Что происходит:**

1. **Категория задачи** (`_categorize_task(goal)`):
   - По ключевым словам и длине текста определяется категория: `fast`, `coding`, `general`, `reasoning`, `planning`, `execution`, `complex` и т.д.
   - От категории зависит, пойдёт ли запрос в Department Heads, делегирование, какой метод (simple/react/extended_thinking и т.д.) будет выбран.

2. **Department Heads (если подходит по категории):**
   - Проверка: нужна ли координация через отделы (`_should_use_department_heads`).
   - Если да — подключается БД экспертов (`DATABASE_URL`), определяется отдел, сложность, при необходимости создаётся промпт для Veronica и запускается распределение задач по отделам (`_execute_department_task` и т.д.).
   - Если там получен результат — он возвращается как ответ, цепочка ниже может не вызываться.

3. **Делегирование Veronica** (`TaskDelegator` + `MultiAgentCollaboration`):
   - Анализ задачи: нужны ли execution, file_operations, research и т.д. (`_should_delegate_task`).
   - Если решено делегировать:
     - Создаётся задача (`delegate_smart(goal)`), выбирается агент (чаще всего Veronica).
     - **Где:** `knowledge_os/app/task_delegation.py`, `knowledge_os/app/multi_agent_collaboration.py`.
     - **Как:** `MultiAgentCollaboration.execute_task(task)` — HTTP `POST` на `VERONICA_URL` (порт 8011) в `/run` с `goal`.
     - Veronica выполняет задачу и возвращает ответ; Victoria кладёт его в результат с пометкой `method: delegation`, статусом и текстом («Выполнено через Veronica», результат).
   - Если делегирование не нужно или не удалось — выполнение продолжает сама Victoria.

4. **Выбор метода** (`_select_optimal_method(category, goal)`):
   - По категории выбирается метод: **simple**, **react**, **extended_thinking**, **swarm**, **tree_of_thoughts**, **hierarchical** и т.д.
   - Сейчас по умолчанию при наличии ReAct используется **react** (в т.ч. для general/fast), чтобы был доступ к инструментам.

5. **Контекст и кэш:**
   - При необходимости подтягивается collective memory, в контекст добавляется `chat_history`.
   - Если включён кэш — проверяется кэш по методу/цели; при попадании возвращается закэшированный результат.

6. **Выполнение выбранного метода** (`_execute_method(method, goal, category, context)`):
   - **react:** вызывается `ReActAgent.run(goal, context)` — цикл «думаю → действие (read_file, list_directory, run_terminal_cmd и т.д.) → наблюдение» до финального ответа. Модель и инструменты — в `knowledge_os/app/react_agent.py`.
   - **simple:** формируется промпт (роль Victoria, контекст, история), запрос в MLX API Server (порт 11435) или Ollama (11434), ответ возвращается как результат. Код — ветка `method == "simple"` в `victoria_enhanced.py`.
   - **extended_thinking:** вызывается `ExtendedThinkingEngine.think(goal, context)` — пошаговое рассуждение, затем финальный ответ. Модель через MLX/Ollama.
   - **delegation:** уже обработано выше (п. 3).
   - Остальные методы (swarm, consensus, hierarchical и т.д.) — свои вызовы соответствующих компонентов.

7. **Итог:**
   - Возвращается словарь: `result` (текст ответа), `method` (какой метод сработал), `metadata` (модель, источник, при делегировании — delegated_to, task_id и т.д.).

---

## 4. Ответ возвращается на сервер Victoria

**Где:** тот же `victoria_server.py`.

**Что происходит:**
- Из результата Enhanced берётся `result`, `method`, `metadata`, `delegated_to`, `task_id` (если есть).
- Формируется **TaskResponse:** `status="success"`, `output=<текст>`, `knowledge={<метаданные>}`.
- В **синхронном** режиме этот ответ сразу уходит клиенту (чат/API).
- В **асинхронном** режиме результат записывается в `_run_task_store[task_id]` (`status: completed`, `output`, `knowledge`), а клиент получает его, опрашивая `GET /run/status/{task_id}`.

---

## 5. Чат получает и показывает результат

**Где:** `scripts/victoria_chat.py` (или фронт/другой клиент).

**Что происходит:**
- При **async:** после 202 чат периодически вызывает `GET /run/status/{task_id}`; при `status=completed` читает `output` и `knowledge`, выводит ответ Victoria, метод, «Выполнено через: …» (если было делегирование).
- При **sync:** из тела ответа `POST /run` сразу берутся `output` и `knowledge` и выводятся так же.
- Текст ответа при необходимости переносится по ширине терминала; сообщение и ответ сохраняются в `chat_history` для следующих запросов.

---

## Краткая схема «кто что где»

| Этап | Кто/что | Где (файл/сервис) |
|------|---------|-------------------|
| Запрос | Ты → чат/API | victoria_chat.py или frontend |
| Приём | Victoria HTTP API | victoria_server.py, POST /run |
| Контекст и безопасность | Сервер | victoria_server.py (project_context, project_prompt) |
| Категория и метод | Victoria Enhanced | victoria_enhanced.py (_categorize_task, _select_optimal_method) |
| Department Heads (если нужно) | Victoria + БД экспертов | victoria_enhanced.py, department_heads_system |
| Делегирование (если нужно) | TaskDelegator, MultiAgentCollaboration | task_delegation.py, multi_agent_collaboration.py |
| Выполнение Veronica | Veronica Agent | HTTP :8011 /run |
| ReAct (файлы, команды) | ReActAgent | react_agent.py, MLX/Ollama |
| Simple (только текст) | Victoria Enhanced | victoria_enhanced.py, MLX API / Ollama |
| Extended Thinking | ExtendedThinkingEngine | extended_thinking.py |
| Ответ пользователю | Сервер → чат | TaskResponse → victoria_chat.py, вывод в терминал |

---

## 6. Делегирование: как решается, куда уходит, что делается

**Кто решает:** Victoria Enhanced в `solve()` через `_should_delegate_task` и **TaskDelegator**.

**Шаги:**

1. **Анализ задачи** — `TaskDelegator.analyze_task(goal)`:
   - По ключевым словам определяются `required_capabilities`: planning, execution, file_operations, research, coordination, code_analysis, system_admin.
   - Примеры: «создай файл», «прочитай», «выполни команду», «найди», «исследова» → чаще execution/file_operations/research.

2. **Выбор агента** — `TaskDelegator.select_best_agent(requirements)`:
   - **Victoria** — planning, reasoning, coordination, code_analysis (эффективность 0.85–0.98).
   - **Veronica** — execution, file_operations, research, system_admin (0.85–0.98).
   - Считается score по требуемым способностям и загрузке; выбирается агент с максимальным score. Часто при execution/file/research это **Veronica**.

3. **Создание задачи** — `TaskDelegator.delegate_smart(goal)`:
   - Вызывает `MultiAgentCollaboration.delegate_task(goal, preferred_agent=best_agent, priority)`.
   - Создаётся `Task` с `task_id`, `goal`, `assigned_to` (Victoria или Veronica), `task_type`, `status: pending`.

4. **Выполнение** — `MultiAgentCollaboration.execute_task(task)`:
   - Определяется **URL агента:**
     - `assigned_to == "Victoria"` → `VICTORIA_URL` (по умолчанию `http://host.docker.internal:8010` в Docker, `http://localhost:8010` локально).
     - `assigned_to == "Veronica"` → `VERONICA_URL` (по умолчанию `http://host.docker.internal:8011` в Docker, `http://localhost:8011` локально).
   - **HTTP `POST {agent_url}/run`** с телом `{"goal": task.goal}` (timeout 300 сек).
   - Ответ парсится: `output`, `knowledge`; при успехе — `CollaborationResult(success=True, result=...)`, иначе — ошибка.

5. **Обработка результата в Victoria:**
   - При `result.success` — возврат из `solve()` с `method: "delegation"`, `delegated_to: task.assigned_to`, `task_id`, текстом вида «✅ Задача выполнена через {Veronica|Victoria}», затем результат агента.
   - При ошибке (HTTP, таймаут, исключение) — логируется, делегирование считается неудачным; Victoria продолжает выполнение **сама** (выбор метода: react, simple, extended_thinking и т.д.).

**Куда уходит делегирование:**

| Кому делегировано | URL | Кто обрабатывает |
|-------------------|-----|-------------------|
| Victoria | `VICTORIA_URL` (8010) `/run` | Victoria Agent (тот же сервер или отдельный инстанс) |
| Veronica | `VERONICA_URL` (8011) `/run` | Veronica Agent |

**Итог:** делегирование решается по анализу задачи и профилям агентов; выполнение — через HTTP POST на `/run` выбранного агента. Ответ возвращается в Victoria и далее пользователю.

---

## 7. Оркестратор: кто такой и что делает

В коде есть **два разных «оркестратора»**. Не путать.

### 7.1. Victoria как оркестратор (оркестрация пользовательских задач)

**Где:** `src/agents/bridge/victoria_server.py` — `VictoriaAgent.orchestrate_task(goal)`, плюс при использовании Enhanced — вся логика в `victoria_enhanced.solve()`.

**Что делает:**
- Принимает **твою** задачу (через `POST /run` или `POST /orchestrate`).
- Анализирует сложность и категорию (`_assess_complexity`, `_categorize_task`).
- **Простая задача:** выбирает одного эксперта или выполняет сама (через `run()` или Enhanced `solve()`).
- **Сложная задача:** Swarm — несколько экспертов параллельно (`run_smart_agent_async` по экспертам), сбор ответов, синтез.
- Решает: Department Heads, делегирование Veronica/Victoria или свой метод (react, simple, extended_thinking и т.д.).
- Отдаёт финальный ответ в `TaskResponse` → чат/API.

То есть **оркестратор пользовательского запроса** — это сама Victoria (Agent + Enhanced): она «дирижирует» категорией, делегированием, выбором метода и сбором результата.

### 7.2. Enhanced Orchestrator (фоновый цикл по задачам из БД)

**Где:** `knowledge_os/app/enhanced_orchestrator.py` — `run_enhanced_orchestration_cycle()`.

**Что делает:**
- Работает **отдельно** от твоего чата с Victoria. Запускается по расписанию или вручную (например, через `telegram_simple` или скрипты).
- Читает **задачи из БД** (`tasks`): приоритизация, выбор задач без исполнителя (`assignee_expert_id IS NULL`).
- **Фазы:** авто-фикс ошибок, миграции, приоритизация, назначение экспертам (`assign_task_to_best_expert`), обновление очередей.
- Назначенные задачи выполняет **Smart Worker** (`smart_worker_autonomous` и др.): опрос БД, вызов `run_smart_agent_async` по экспертам, сохранение результата в БД.
- Victoria **как сервис** может использоваться внутри (например, эксперты или агенты вызывают LLM), но **точка входа** — не твой запрос в чат, а цикл по таблице `tasks`.

**Кратко:**

| | Victoria как оркестратор | Enhanced Orchestrator |
|---|--------------------------|------------------------|
| **Триггер** | Твой запрос в чат/API (`/run`, `/orchestrate`) | Фоновый цикл по БД |
| **Вход** | `goal` из запроса | Записи в `tasks` |
| **Выход** | Ответ тебе в чат | Обновление `tasks`, отчёты |
| **Роль** | Оркестрация **твоего** запроса, делегирование, выбор метода | Оркестрация **очереди задач** корпорации, назначение экспертам |

---

## Где что лежит (кратко)

- **Вход в Victoria:** `src/agents/bridge/victoria_server.py` — `run_task`, при async — `_run_task_background`.
- **Логика Victoria:** `knowledge_os/app/victoria_enhanced.py` — `solve`, категории, метод, вызов ReAct/simple/delegation и т.д.
- **Делегирование:** `knowledge_os/app/task_delegation.py` (TaskDelegator: `analyze_task`, `select_best_agent`, `delegate_smart`), `knowledge_os/app/multi_agent_collaboration.py` (`delegate_task`, `execute_task` — HTTP POST на Victoria/Veronica `/run`).
- **URL агентов:** `VICTORIA_URL` (8010), `VERONICA_URL` (8011); в Docker — `host.docker.internal`, локально — `localhost`.
- **Victoria как оркестратор:** `victoria_server.py` — `orchestrate_task`, плюс `victoria_enhanced.solve()` (категория, делегирование, метод).
- **Enhanced Orchestrator (БД-цикл):** `knowledge_os/app/enhanced_orchestrator.py` — `run_enhanced_orchestration_cycle`, назначение задач экспертам, Smart Worker.
- **ReAct (инструменты):** `knowledge_os/app/react_agent.py`.
- **Простой ответ (LLM без инструментов):** ветка `method == "simple"` в `victoria_enhanced.py`, запросы к MLX (11435) / Ollama (11434).
- **Статус фоновой задачи:** `GET /run/status/{task_id}` в `victoria_server.py`, хранилище `_run_task_store`.
- **Чат:** `scripts/victoria_chat.py` — отправка запроса, при async — опрос статуса, вывод результата.

Так устроен полный процесс от твоего запроса до выполнения задачи и ответа в чате.

---

## Проверка живой цепочки

Чтобы проверить всю цепочку на реальных сервисах (без моков):

1. **Запустите Knowledge OS** (Victoria, БД, при необходимости Veronica):
   ```bash
   docker-compose -f knowledge_os/docker-compose.yml up -d
   ```
   На сервере Victoria должны быть: `USE_VICTORIA_ENHANCED=true`, `DATABASE_URL` (PostgreSQL с экспертами).

2. **Запустите тест живой цепочки** (один sync-запрос «Помоги с анализом данных»):
   ```bash
   cd knowledge_os && make test-live-chain
   ```
   или:
   ```bash
   cd knowledge_os && python scripts/run_live_chain_test.py
   ```
   Ожидание: HTTP 200, `status=success`, непустой `output`, в `knowledge.method` при проходе через отделы — `department_heads` или `task_distribution`.

3. **Интеграционные тесты pytest** (те же проверки + async-режим):
   ```bash
   cd knowledge_os && ./scripts/run_tests_with_db.sh tests/test_live_chain.py -v -m integration
   ```
   Если Victoria недоступна, тесты с маркером `integration` будут пропущены (skip).
