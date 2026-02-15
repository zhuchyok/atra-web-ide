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

## 7. Итог

| Компонент | Использует базу знаний? | Как |
|-----------|-------------------------|-----|
| **Victoria** | Да | _get_knowledge_context (RAG+ / ILIKE) в victoria_server |
| **Veronica** | Да | get_knowledge_context_veronica (ILIKE) в server.py |
| **Оркестраторы** | Да | через run_smart_agent_async → _get_knowledge_context в ai_core |
| **Эксперты** | Да | через run_smart_agent_async (тот же путь) |
| **Воркер задач** | Да | run_smart_agent_async при исполнении задачи |
| **Telegram** | Да | search_knowledge в telegram_gateway |

База знаний, которая ежедневно накапливается, **активно используется** Victoria, Veronica, оркестраторами и экспертами через описанные точки входа.
