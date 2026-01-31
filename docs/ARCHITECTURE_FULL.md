# Полная структура системы (с учётом всех изменений из чатов)

Один документ со схемой: пользователь → точки входа → Victoria (8010, три уровня) → делегирование / Department Heads / оркестратор БД → исполнители и обратно.

**Полная архитектура проекта (структура, порты, запуск, API, метрики, Cursor, команда):** **`docs/PROJECT_ARCHITECTURE_AND_GUIDE.md`**.

**Статус:** Архитектура **рабочая и оптимальная**: внедрены рекомендации — (1) план от Victoria называется task_plan и при наличии возвращается структурированный task_plan_struct; (2) Task Distribution использует task_plan_struct без повторного вызова Victoria для парсинга; (3) в цепочке БД Smart Worker проверяет результат через общий валидатор перед отметкой completed. Обратная совместимость: ключ veronica_prompt в coordination_result по-прежнему поддерживается.

---

## Схема (ASCII)

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    ПОЛЬЗОВАТЕЛЬ                          │
                    └─────────────────────────┬───────────────────────────────┘
                                             │
            ┌────────────────────────────────┼────────────────────────────────┐
            │                                │                                │
            ▼                                ▼                                ▼
   ┌─────────────────┐            ┌─────────────────┐            ┌─────────────────┐
   │  Чат / API       │            │  Задачи в БД    │            │  Telegram и др. │
   │  (backend chat,  │            │  (tasks table)   │            │  (gateway)      │
   │   POST /api/chat)│            │  assignee=NULL  │            │                 │
   └────────┬────────┘            └────────┬────────┘            └────────┬────────┘
            │                               │                               │
            │ POST :8010/run                │ цикл по БД                    │ → POST :8010/run
            │ (goal, project_context)       │                               │   или в БД
            ▼                               ▼                               ▼
   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │              Victoria Agent — ОДИН сервис на порту 8010 (victoria-agent)         │
   │  ┌─────────────┬─────────────────────────────┬─────────────────────────────────┐  │
   │  │ Agent       │ Enhanced                   │ Initiative                      │  │
   │  │ (всегда)    │ (USE_VICTORIA_ENHANCED)    │ (ENABLE_EVENT_MONITORING)       │  │
   │  │ база: чат,  │ ReAct, Extended Thinking,  │ Event Bus, File Watcher,        │  │
   │  │ планирование│ Swarm, Consensus,          │ Service Monitor, Deadline       │  │
   │  │             │ Department Heads,          │ Tracker, Skill Registry,        │  │
   │  │             │ делегирование Veronica,    │ автозапуск MLX при падении      │  │
   │  │             │ выбор модели Ollama/MLX    │                                 │  │
   │  └─────────────┴─────────────────────────────┴─────────────────────────────────┘  │
   │  При получении задачи: ensure_llm_backends (проверка Ollama/MLX, при необходимости │
   │  поднять MLX через Supervisor, ollama serve; инвалидация кэша available_models_   │
   │  scanner при запуске бэкенда; обновить кэш LocalAIRouter — список живых узлов)   │
   └─────────────────────────────┬─────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────┐      ┌─────────────────┐      ┌─────────────────────────────┐
   │ Department  │      │ Делегирование    │      │ Сама Victoria               │
   │ Heads       │      │ → Veronica (8011)│      │ (react, simple,             │
   │ (если       │      │ (найди, выполни, │      │  extended_thinking, swarm)  │
   │  просьба,   │      │  file_ops,       │      │                             │
   │  не чат)    │      │  research)       │      │                             │
   │             │      │ POST :8011/run   │      │                             │
   └──────┬──────┘      └────────┬────────┘      └──────────────┬──────────────┘
          │                      │                             │
          │ determine_department │                             │
          │ task_plan (создаёт    │                             │
          │ Victoria, не Veronica)│                             │
          ▼                      ▼                             │
   ┌─────────────────┐   ┌─────────────────┐                  │
   │ Task            │   │ Veronica Agent  │                  │
   │ Distribution    │   │ (порт 8011)      │                  │
   │ (БД экспертов,  │   │ Local Developer │                  │
   │  распределение  │   │ выполнение      │                  │
   │  → выполнение   │   │ → ответ         │                  │
   │  экспертами)    │   └────────┬────────┘                  │
   └────────┬────────┘            │                             │
            │                     │                             │
            │ execute_task_       │                             │
            │ assignment          │                             │
            │ → ai_core.          │                             │
            │   run_smart_agent_  │                             │
            │   async(expert_name)│                             │
            ▼                     │                             ▼
   ┌─────────────────┐            │                  ┌─────────────────────────┐
   │ experts (БД)    │            │                  │ ai_core / LocalAIRouter │
   │ сотрудники      │            │                  │ (выбор модели из        │
   │ отделов         │            │                  │  доступных Ollama/MLX:  │
   └────────┬────────┘            │                  │  check_health,          │
            │                     │                  │  _select_model,         │
            │                     │                  │  available_models_     │
            ▼                     │                  │  scanner)               │
   ┌─────────────────┐            │                  └────────────┬────────────┘
   │ ai_core.        │            │                               │
   │ run_smart_agent_│            │                               │
   │ async(expert_name)            │                               │
   └────────┬────────┘            │                               │
            │                     │                               ▼
            └─────────────────────┼──────────────────► ┌─────────────────────────┐
                                  │                     │ Ollama (11434) /        │
                                  │                     │ MLX API (11435)        │
                                  │                     │ — модели из доступных  │
                                  │                     └─────────────────────────┘
                                  │
            ◄─────────────────────┴────────────────────── ответ пользователю


   ┌─────────────────────────────────────────────────────────────────────────────────┐
   │  Отдельный поток: Enhanced Orchestrator (фоновый цикл по БД, не запрос пользователя) │
   └─────────────────────────────┬─────────────────────────────────────────────────────┘
                                 │
                                 │ run_enhanced_orchestration_cycle()
                                 │ читает tasks (assignee_expert_id IS NULL)
                                 ▼
                        ┌─────────────────┐
                        │ assign_task_to_ │
                        │ best_expert     │
                        │ (domain_id,     │
                        │  workload,      │
                        │  success_rate)  │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ experts (БД)    │
                        │ → лучший эксперт│
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Smart Worker    │
                        │ (process_task)  │
                        │ → ai_core.      │
                        │   run_smart_    │
                        │   agent_async   │
                        └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────────────┐
                        │ LocalAIRouter / Ollama   │
                        │ и MLX (доступные модели) │
                        └─────────────────────────┘
```

**Как эксперты решают задачи:** и Task Distribution (сотрудники отделов), и Smart Worker (Enhanced Orchestrator) вызывают **ai_core.run_smart_agent_async(prompt, expert_name=...)**. Внутри ai_core используется **LocalAIRouter**: `router.run_local_llm(prompt, category=...)` — выбор живых узлов (check_health: MLX 11435, Ollama 11434) и модели по категории (_select_model, OLLAMA_MODELS/MODEL_MAP). То есть эксперты тоже обращаются к **моделям из доступных в Ollama и MLX** (LocalAIRouter, при необходимости available_models_scanner).

**Почему используется сканер моделей (available_models_scanner):** На Ollama и MLX список установленных моделей может меняться (пользователь делает `ollama pull` / удаляет модели). LocalAIRouter и ReActAgent используют фиксированные имена моделей (MODEL_MAP, OLLAMA_MODELS); если такой модели нет на узле, запрос даёт 404. Сканер запрашивает у Ollama и MLX реальный список моделей (`/api/tags`) и возвращает его с кэшем (TTL). Он используется в путях, где нужно выбирать модель из **фактически установленных** (fallback Victoria при ответе без Department Heads, Extended Thinking, Model Selector). При запуске бэкендов в `ensure_llm_backends` кэш сканера инвалидируется, чтобы при следующем вызове `get_available_models()` список был актуальным. Цепочка: пользователь → Victoria (8010) → Department Heads → отдел → эксперт (БД) → ReActAgent.run(goal) → Ollama/MLX — см. также [TASK_ARCHITECTURE_WHY_EMPTY_RESULT.md](TASK_ARCHITECTURE_WHY_EMPTY_RESULT.md).

---

## Кратко по блокам

| Блок | Что делает |
|------|------------|
| **Пользователь** | Чат в Web IDE, API, Telegram, задачи в БД. |
| **Чат/API** | Backend проксирует запрос на Victoria: `POST http://localhost:8010/run` с `goal`, `project_context`. |
| **Victoria (8010)** | Один сервис, три уровня: Agent (база), Enhanced (ReAct, Department Heads, делегирование, выбор модели), Initiative (Event Bus, мониторинг, skills). При получении задачи — проверка/запуск Ollama и MLX. |
| **Department Heads** | Если запрос — просьба (не чат): отдел (Strategy/Data и др.), Task Distribution, эксперты из БД → выполнение → сбор → синтез Victoria. |
| **Делегирование** | Если задача на поиск/исполнение/file_ops → Veronica (8011), ответ возвращается в Victoria → пользователю. |
| **Сама Victoria** | react, simple, extended_thinking, swarm; модель выбирается из доступных Ollama/MLX. |
| **Veronica (8011)** | Выполняет переданную задачу, отдаёт результат обратно в Victoria. |
| **Эксперты (Task Distribution, Smart Worker)** | Решают задачи через **ai_core.run_smart_agent_async** → **LocalAIRouter.run_local_llm** → модели из доступных **Ollama (11434) и MLX (11435)** (check_health, _select_model, при необходимости available_models_scanner). |
| **Enhanced Orchestrator** | Фоновый цикл по таблице `tasks` (без исполнителя), назначение лучшему эксперту, Smart Worker → ai_core → Ollama/MLX, обновление БД. |

---

## Кто распределяет задачи, кто проверяет, кто пишет промпты

- **Victoria** — решает, как обрабатывать запрос (чат / просьба по отделам / делегировать Veronica / сама). **Пишет план задачи** (декомпозиция, отделы, подзадачи) для системы распределения. В коде план называется `veronica_prompt`, но **создаёт его Victoria**, не Veronica. Veronica (8011) промпты для других **не пишет** — только выполняет задачи от Victoria.
- **Task Distribution** (в процессе Victoria) — **распределяет** подзадачи по экспертам по плану Victoria; **проверяет** результат через `manager_review_task` (управляющий отдела или Victoria по умолчанию).
- **Veronica (8011)** — только **исполнитель**: получает от Victoria конкретную задачу, выполняет, возвращает ответ. Не распределяет и не пишет промпты для других.
- **Enhanced Orchestrator** — **распределяет** задачи из БД одному эксперту (`assign_task_to_best_expert`). **Проверки** после выполнения Smart Worker **нет** — это возможное улучшение (см. `docs/ORCHESTRATION_IMPROVEMENTS.md`).
- **Smart Worker** — выполняет назначенные задачи из БД, помечает `completed`. Проверку не делает.

Подробный разбор и рекомендации: **`docs/ORCHESTRATION_IMPROVEMENTS.md`**.

---

## Кто выполняет задачу и кто кому докладывает

**Два разных сценария:**

### 1. Department Heads (method: department_heads)

- **Кто выполняет:** «Сотрудники» — эксперты из БД (например Даниил, директора отделов). Их **роли** выполняются **внутри процесса Victoria** через **локальные модели**: `task_dist.execute_task_assignment()` вызывает `ai_core.run_smart_agent_async(prompt, expert_name=...)` → LocalAIRouter → Ollama/MLX. Отдельный сервис Veronica (8011) **не вызывается**.
- **Кто кому докладывает:** Управляющий проверяет результат (локально), Department Head собирает ответы (локально), **Victoria синтезирует** финальный ответ и отдаёт пользователю. То есть «доложила» не Veronica, а сама Victoria после сбора результатов от «сотрудников» (локальных вызовов LLM под маской экспертов).

**Итог:** Задача решена сотрудниками (экспертами) через **локальные модели** в процессе Victoria; Veronica в этой цепочке не участвует.

**Ответ пользователю при method=department_heads:** Текст ответа берётся в таком порядке: (1) `final_reflection` из возврата ReActAgent; (2) при пустом — `observation` или `reflection` последнего шага; (3) при пустом или подставной строке — агрегация из шагов с действиями `create_file`/`write_file` (их `observation`, лимит длины); (4) при полном пустом результате — подставная строка «Задача выполнена экспертом … (статус: …)»; (5) если эта подставная строка соответствует «пустому успеху» (модель вызвала finish без результата), пользователю отдаётся честное сообщение о том, что эксперт не вернул вывод, с рекомендацией переформулировать или разбить задачу. Подробнее: [TASK_ARCHITECTURE_WHY_EMPTY_RESULT.md](TASK_ARCHITECTURE_WHY_EMPTY_RESULT.md).

### 2. Делегирование (method: delegation)

- **Кто выполняет:** Victoria через TaskDelegator решает отдать задачу **Veronica** (по ключевым словам: выполни, файл, найди и т.д.). Запрос уходит по **HTTP на порт 8011** (`POST VERONICA_URL/run`). Выполняет уже **сервис Veronica** (свои модели/инструменты).
- **Кто кому докладывает:** Veronica выполняет задачу и **возвращает результат в Victoria**; Victoria отдаёт ответ пользователю. Здесь да — **Veronica доложила Victoria о выполнении**, Victoria отдала результат пользователю.

**Итог:** В наших тестах (план по читаемости, рекомендации по надёжности, принципы чистой архитектуры) срабатывали **ReAct** и **Department Heads** — в обоих случаях всё выполнялось **локальными моделями в процессе Victoria**, без вызова Veronica (8011). Путь «Veronica выполнила и доложила Victoria» срабатывает только когда Victoria выбирает **делегирование** (например задача на выполнение кода, файлы, поиск).

---

## Порты и сервисы

| Порт | Сервис | Роль |
|------|--------|------|
| 8010 | victoria-agent | Victoria Agent + Enhanced + Initiative (один процесс). |
| 8011 | veronica-agent | Veronica, Local Developer. |
| 11434 | Ollama | LLM (при необходимости поднимается `ollama serve`). |
| 11435 | MLX API Server | LLM (при необходимости поднимается MLX Server Supervisor). |
| 5432 | PostgreSQL | БД (experts, tasks, knowledge_nodes и др.). |

---

## Файлы (где что лежит)

| Что | Где |
|-----|-----|
| Точка входа Victoria HTTP | `src/agents/bridge/victoria_server.py` (lifespan, POST /run, GET /status). |
| Три уровня Victoria | Там же: Agent — класс VictoriaAgent; Enhanced + Initiative — VictoriaEnhanced() и start(). |
| **Пайплайн VictoriaAgent (мировая практика)** | **Understand** (`understand_goal`) → переформулировать запрос под модули; **Plan** по переформулированной цели; **Execute** с подсказкой первого шага. См. `VictoriaAgent.run()` и `docs/VICTORIA_PROCESS_FULL.md`. |
| Логика solve(), Department Heads, делегирование | `knowledge_os/app/victoria_enhanced.py`. |
| Проверка/запуск Ollama и MLX при задаче | `knowledge_os/app/llm_backends_ensure.py`, вызов в начале solve(). |
| Выбор модели из Ollama/MLX | `knowledge_os/app/local_router.py`, `knowledge_os/app/available_models_scanner.py`. |
| Эксперты и Smart Worker → модели | `knowledge_os/app/ai_core.py` (run_smart_agent_async использует LocalAIRouter.run_local_llm); Task Distribution и Enhanced Orchestrator вызывают ai_core. |
| Department Heads, Task Distribution | `knowledge_os/app/department_heads_system.py`, `knowledge_os/app/task_distribution_system.py`, `task_distribution_system_complete.py` (execute_task_assignment → run_smart_agent_async). |
| Делегирование Veronica | `knowledge_os/app/task_delegation.py`, `knowledge_os/app/multi_agent_collaboration.py`. |
| Enhanced Orchestrator | `knowledge_os/app/enhanced_orchestrator.py` (run_enhanced_orchestration_cycle, assign_task_to_best_expert, Smart Worker). |
| Telegram → Victoria | `src/agents/bridge/victoria_telegram_bot.py` (опрос getUpdates, POST на VICTORIA_URL:8010/run). |
| Web Chat → Victoria / MLX | `backend/app/routers/chat.py` (use_victoria → VictoriaClient → 8010; fallback или use_victoria=False → MLX). |
| Backend → Victoria | `backend/app/services/victoria.py` (VictoriaClient, base_url=8010). |

---

## Все каналы входа (пользователь → система)

Пользователь обращается к системе через любой из каналов; **единая точка входа агентской логики — Victoria (порт 8010)**. Veronica (8011) вызывается только Victoria, не напрямую пользователем.

| Канал | Как запрос попадает в систему | Куда идёт запрос |
|-------|-------------------------------|-------------------|
| **Web Chat** (Web IDE) | Frontend → Backend `POST /api/chat` | При `use_victoria=True`: Backend → Victoria (8010). Иначе или fallback: Backend → MLX API (11435). |
| **Telegram** | Пользователь пишет боту → `victoria_telegram_bot` опрашивает getUpdates | Бот → `POST VICTORIA_URL/run` (обычно 8010). |
| **Cursor (IDE)** | Запросы из Cursor (чаты, агент) через API или скрипты | Если бэкенд Web IDE: как Web Chat → Victoria (8010). Прямые скрипты: `POST http://localhost:8010/run`. |
| **Терминал / скрипты** | curl, Python-скрипты, cron | `POST http://localhost:8010/run` (goal, project_context) или запись в БД `tasks`. |
| **Облачные API / внешние вызовы** | Внешние сервисы по API | На Victoria URL (8010) или на Backend → проксирование на Victoria. |
| **Задачи в БД** | Создание записей в таблице `tasks` (assignee_expert_id = NULL) | Два потока: (1) Enhanced Orchestrator в фоне читает БД и назначает задачи экспертам (Smart Worker); (2) при необходимости задачи могут обрабатываться через вызов Victoria (зависит от интеграции). |

Итог: **все каналы ведут к Victoria (8010)** или к Backend/MLX (обходной путь для простого чата). Victoria решает: Department Heads, делегирование Veronica (8011) или выполнение сама (ReAct, simple, swarm).

---

## Параллелизм и порядок выполнения

- **Порядок может меняться** в зависимости от типа запроса (casual chat → без Department Heads; просьба → Department Heads; выполни/файлы → делегирование Veronica).
- **Параллелизм:**
  - **Enhanced Orchestrator** работает **параллельно** пользовательским запросам: фоновый цикл по БД, назначение задач экспертам, Smart Worker — независимый поток.
  - **Внутри одного запроса Victoria (Department Heads):** назначения нескольким экспертам выполняются **параллельно** (`asyncio.gather` в `victoria_enhanced.py`: execution_tasks, затем review_tasks).
  - **Swarm / Consensus:** несколько агентов или моделей могут вызываться параллельно (asyncio.gather).
  - **Локальные модели:** один запрос к LLM в данный момент на эксперта; параллелизм — по разным экспертам/подзадачам.
- **Цепочка по шагам (логический порядок):**  
  Пользователь → [канал] → **Victoria (8010)** → (1) Department Heads → отделы → эксперты (БД) → ai_core → Ollama/MLX **или** (2) делегирование → **Veronica (8011)** → выполнение → ответ Victoria **или** (3) сама Victoria (ReAct/simple/swarm) → ai_core → Ollama/MLX.  
  Отдельно: **Enhanced Orchestrator** (БД → назначение лучшему эксперту → Smart Worker → ai_core → Ollama/MLX).

---

## Мировые практики (сравнение)

- **Hierarchical orchestration (Anthropic):** изолированные контексты, супервизор координирует подзадачи — у нас: Victoria как супервизор, Department Heads и делегирование Veronica.
- **Supervisor–Worker (Meta, LangGraph):** один координатор, воркеры выполняют шаги — у нас: Victoria координатор, эксперты (Task Distribution) и Veronica как воркеры.
- **Event-driven и проактивность:** мониторинг сервисов, автозапуск MLX/Ollama при падении, Event Bus, File Watcher — Victoria Initiative.
- **Локальные модели в приоритете, облако как fallback:** LocalAIRouter (Ollama 11434, MLX 11435), при недоступности — cursor-agent/облако (ai_core).
- **Единая точка входа для агентов (Victoria), специализированный исполнитель (Veronica):** соответствует практике разделения «менеджер — исполнитель» в мультиагентных системах.

---

## Рекомендации по улучшению структуры (внедрено)

1. **План от Victoria (task_plan)** — в коде и coordination_result используются `task_plan` и `task_plan_struct`; обратная совместимость: ключ `veronica_prompt` по-прежнему поддерживается.
2. **Проверка в цепочке БД** — Smart Worker перед отметкой `completed` вызывает общий валидатор `task_result_validator.validate_task_result`; при провале задача остаётся в `pending` для повторной попытки.
3. **План в JSON без повторного парсинга** — Victoria возвращает `(task_plan_text, task_plan_struct)`; при наличии `task_plan_struct` Task Distribution вызывает `distribute_tasks_from_plan()` без повторного вызова Victoria.

Опционально (не внедрено): декомпозиция сложных задач из БД через один вызов Victoria. Подробно: **`docs/ORCHESTRATION_IMPROVEMENTS.md`**.
