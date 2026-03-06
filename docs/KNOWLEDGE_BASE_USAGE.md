# Использование базы знаний (knowledge_nodes) в корпорации

**Вопрос:** база знаний, которая ежедневно накапливается, активно используется Victoria, Veronica, оркестраторами и экспертами?

**Ответ: да.** Ниже — кто и как подключает knowledge_nodes (и RAG) к ответам.

**Обновлено:** 2026-02-09

---

## 1. Victoria

- **Где:** `src/agents/bridge/victoria_server.py`
- **Как:** перед формированием промпта вызывается `_get_knowledge_context(goal)` — векторный поиск (RAG+) по эмбеддингам + при отсутствии эмбеддингов ILIKE по `knowledge_nodes`. Результат подставляется в промпт как блок «Релевантные знания».
- **Дополнительно:** предзагрузка кэша RAG типовыми запросами при старте (`RAG_PRELOAD_TYPICAL_QUERIES`), один эмбеддинг на запрос (RAG_PLUS_ROCKET_SPEED).

---

## 2. Veronica

- **Где:** `src/agents/bridge/server.py` — `get_knowledge_context_veronica(goal)`
- **Как:** при `USE_KNOWLEDGE_OS` и доступном пуле БД выполняется запрос к `knowledge_nodes` (ILIKE по цели, `confidence_score > 0.3`, лимит 5). Текст блока «РЕЛЕВАНТНЫЕ ЗНАНИЯ ИЗ БАЗЫ КОРПОРАЦИИ» добавляется в промпт перед вызовом модели.
- **Итог:** та же БД knowledge_nodes, что и у Victoria; ежедневно накапливаемые узлы участвуют в ответах Veronica.

---

## 3. Оркестраторы и эксперты (run_smart_agent_async)

- **Где:** `knowledge_os/app/ai_core.py` — `run_smart_agent_async()`
- **Как:** перед вызовом LLM вызывается `_get_knowledge_context(user_part)` — выборка из `knowledge_nodes` (векторный поиск при наличии эмбеддингов, иначе ILIKE). Контекст добавляется в `full_prompt` и в кэш (semantic_ai_cache).
- **Кто этим пользуется:** Victoria Enhanced (swarm, consensus, react), воркер (исполнение задач из БД), оркестраторы и любые вызовы `run_smart_agent_async` (в т.ч. эксперты по имени). То есть оркестраторы и эксперты получают базу знаний через общий слой ai_core.

---

## 4. Telegram-шлюз

- **Где:** `knowledge_os/app/telegram_gateway.py` — `handle_message()`
- **Как:** перед ответом вызывается `search_knowledge(user_text, domain_hint, limit=5)`; результат передаётся в промпт как «ЗНАНИЯ».

---

## 5. Другие потребители knowledge_nodes

- **anti_hallucination.py** — `retrieve_relevant_context()`: выборка из `knowledge_nodes` (ILIKE, is_verified, confidence).
- **model_enhancer.py** — `EnhancedRAGEngine.retrieve_enhanced_context()`: выборка из `knowledge_nodes` (ключевые слова, реранкинг).
- **contextual_learner** — связь `interaction_logs` с `knowledge_nodes` по `knowledge_id`; обучение на обратной связи.

---

## 6. Откуда появляются узлы (ежедневное накопление)

- Завершённые задачи (smart_worker, отчёты) → запись в knowledge_nodes (в т.ч. embedding при наличии).
- Nightly Learner, дебаты, гипотезы, решения Совета → запись в knowledge_nodes.
- Эталоны куратора → `curator_add_standard_to_knowledge.py` пишет в knowledge_nodes (домен curator_standards).
- Victoria `_learn_from_task` → запись в knowledge_nodes (домен **victoria_tasks**: задача + результат).
- Ручное добавление, миграции, импорт.

**Runbook по типу задачи:** для типовых запросов (статус, что умеешь, привет, список файлов) эталоны в **curator_standards**; для «похожих успешных решений» Victoria Enhanced подтягивает до 2 записей из **victoria_tasks**. При выборе узлов используется приоритет **usage_count** (чаще используемое — выше в выдаче). См. HOW_TO_INDEX «Runbook по типу задачи».

---

## 6.1. Знания гигантов (AI Research) и самообучение Виктории

**Вопрос:** Виктория изучает знания гигантов? Настраивали ли мы, чтобы она сама самообучалась и самосовершенствовалась?

**Ответ:**

- **Знания гигантов в ответах:** Да. Виктория подтягивает их двумя способами:
  1. **Общий RAG** — `_get_knowledge_context(goal)` возвращает релевантные узлы из `knowledge_nodes` по смыслу (векторный поиск / ILIKE). Если в БД проиндексированы документы из `docs/COGNITIVE_CODE.md`, `knowledge_os/knowledge_base/ai_research/` или эталоны куратора, они попадают в блок «Релевантные знания» при релевантном запросе.
  2. **Явный блок AI Research** — при запросах с ключевыми словами (anthropic, google, openai, research, исследования и т.д.) вызывается `VictoriaEnhanced._get_ai_research_context(goal)`: выборка из `knowledge_nodes` по домену **AI Research** или `metadata->>'source' = 'external_docs_indexer'`. Используется в стриминге и в Enhanced-оркестрации.

- **Откуда в БД попадают «гиганты»:**
  - Скрипт **index_external_docs.py** качает репозитории (например system_prompts_leaks) в `knowledge_base/ai_research/` и пишет чанки в `knowledge_nodes` (домен AI Research). Запуск — вручную или по крону.
  - Эталоны куратора → домен **curator_standards**.
  - **index_cognitive_code.py** — индексирует `docs/COGNITIVE_CODE.md` (и опционально другие доки) в knowledge_nodes (домен AI Research). Запуск: `cd knowledge_os && .venv/bin/python scripts/index_cognitive_code.py`; см. HOW_TO_INDEX «Знания гигантов в RAG».

- **Самообучение и самосовершенствование:** Да, настроено, но без отдельного шага «каждую ночь читать COGNITIVE_CODE».
  - **Victoria** — `_learn_from_task`: после задач пишет в knowledge_nodes (домен **victoria_tasks**); эти узлы потом подтягиваются в RAG.
  - **Nightly Learner** — обучает экспертов на опыте (contextual_learner), обновляет знания и промпты через **knowledge_applicator** (уроки → guidance, ретроспективы → knowledge_nodes, топ-инсайты → задачи на эволюцию промптов).
  - **CorporationSelfLearning** — анализ ошибок и метрик, генерация и применение улучшений.
  - Знания гигантов участвуют в самообучении **косвенно**: если контент AI Research / COGNITIVE_CODE лежит в knowledge_nodes, он попадает в RAG при ответах и в выборки по инсайтам (knowledge_applicator смотрит все домены). Отдельного «ночного чтения» файлов COGNITIVE_CODE или ai_research для самосовершенствования сейчас нет.

**Чтобы Виктория активнее «изучала гигантов» для самосовершенствования:** (1) убедиться, что ai_research и при необходимости COGNITIVE_CODE проиндексированы в knowledge_nodes (запуск index_external_docs, при необходимости — индексация выбранных доков из docs/); (2) при желании добавить в nightly/knowledge_applicator шаг «подтягивать топ-N узлов из домена AI Research или curator_standards в задачи на эволюцию промптов/экспертов». См. также docs/plans/2026-02-23-expert-and-brainstorm-design.md и .cursor/rules/expert_and_brainstorm.mdc (в Cursor при /expert явно подключаются COGNITIVE_CODE и знания гигантов).

---

## 6.2. Сотрудники, оркестраторы и агенты — те же знания гигантов

**Вопрос:** получают ли знания гигантов сотрудники (эксперты), оркестраторы и агенты?

**Ответ: да.** Все вызовы через **run_smart_agent_async** (ai_core) получают один и тот же блок контекста из **\_get_knowledge_context**: выборка из `knowledge_nodes` по доменам **AI Research**, **victoria_tasks**, по метаданным **external_docs_indexer** и **autonomous_worker**. То есть оркестраторы (Enhanced, Streaming, Swarm, Council и др.), эксперты по имени, воркер задач, Telegram-шлюз и любые агенты, идущие через ai_core, получают в промпт блок «📚 [KNOWLEDGE CONTEXT (AI Research & Corp)]» с релевантными чанками, в том числе знания гигантов (если они проиндексированы в этих доменах). Отдельный ключевыми-словами блок **\_get_ai_research_context** есть только у Виктории при стриминге/Enhanced; для остальных достаточно общего RAG в ai_core. Список «кто коллеги» для делегирования оркестраторам и Виктории даёт **expert_services** (employees.json + эксперты из БД).

---

## 7. Итог

| Компонент        | Использует базу знаний? | Как                                                             |
| ---------------- | ----------------------- | --------------------------------------------------------------- |
| **Victoria**     | Да                      | \_get_knowledge_context (RAG+ / ILIKE) в victoria_server        |
| **Veronica**     | Да                      | get_knowledge_context_veronica (ILIKE) в server.py              |
| **Оркестраторы** | Да                      | через run_smart_agent_async → \_get_knowledge_context в ai_core |
| **Эксперты**     | Да                      | через run_smart_agent_async (тот же путь)                       |
| **Воркер задач** | Да                      | run_smart_agent_async при исполнении задачи                     |
| **Telegram**     | Да                      | search_knowledge в telegram_gateway                             |

База знаний, которая ежедневно накапливается, **активно используется** Victoria, Veronica, оркестраторами и экспертами через описанные точки входа.

---

## 8. Знания гигантов (AI Research) и самообучение

### Использует ли Виктория знания гигантов?

**Да, в двух режимах:**

1. **RAG по всей базе:** `_get_knowledge_context(goal)` тянет из `knowledge_nodes` по смыслу (эмбеддинг/ILIKE). Если в БД проиндексированы документы из `docs/COGNITIVE_CODE.md`, `knowledge_os/knowledge_base/ai_research/` или эталоны куратора — они попадают в блок «Релевантные знания» при релевантном запросе.
2. **Явный блок AI Research:** при стриминге и в Victoria Enhanced вызывается `_get_ai_research_context(goal)` (`knowledge_os/app/victoria_enhanced.py`): если в запросе есть ключевые слова (anthropic, google, openai, research, Claude, GPT и т.д.), подтягиваются до 3 узлов из домена **AI Research** или с `source = external_docs_indexer` и подставляются как «Актуальные знания AI Research».

**Индексация гигантов в БД:** скрипт `knowledge_os/scripts/index_external_docs.py` выкачивает репозитории (например system_prompts_leaks) в `knowledge_base/ai_research/` и пишет чанки в `knowledge_nodes` (домен AI Research). Запуск — вручную или по крону. Документы из `docs/` (COGNITIVE_CODE, OPENWEBUI_RAG_SETUP) можно индексировать отдельным скриптом или через куратора (curator_standards).

### Самообучение и самосовершенствование

**Что уже настроено:**

- **Victoria `_learn_from_task`** — после успешных задач пишет в `knowledge_nodes` (домен **victoria_tasks**); при похожих запросах эти узлы подтягиваются в RAG.
- **CorporationSelfLearning** — анализирует ошибки и метрики за 24 ч, генерирует и применяет улучшения (параметры, промпты).
- **Nightly Learner** — обучает экспертов на опыте (contextual_learner), обновляет знания и промпты через **knowledge_applicator** (ретроспективы → knowledge_nodes, топ-инсайты → задачи на эволюцию промптов, код-релевантные уроки → задачи «Внедрить в код»).
- **Knowledge applicator** — уроки из adaptive_learning_logs и верифицированные узлы из `knowledge_nodes` (любой домен) превращаются в guidance и в задачи; явного «читаем COGNITIVE_CODE каждую ночь» нет — используются уже записанные в БД узлы.

**Связь «гиганты ↔ самообучение»:** знания гигантов участвуют в ответах Виктории, когда они лежат в `knowledge_nodes` (RAG + при ключевых словах — блок AI Research). Цикл самосовершенствования (nightly, applicator) опирается на то, что уже в БД (ошибки, ретроспективы, инсайты). Чтобы Виктория «регулярно изучала гигантов» для самоулучшения: (1) обеспечить индексацию COGNITIVE_CODE и ai_research в `knowledge_nodes` (разовый или периодический запуск index_external_docs / индексация docs); (2) при желании — добавить в nightly или applicator шаг «топ-N узлов из домена AI Research / curator_standards → задача на обновление guidance или промптов экспертов». Дизайн команд /expert и /brainstorm: `docs/plans/2026-02-23-expert-and-brainstorm-design.md`.
