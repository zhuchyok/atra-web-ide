# Документация по внедрённым улучшениям

## Итог: всё ли сделано?

**Да.** Все три улучшения внедрены и работают в коде:

| Улучшение | Файл | Статус |
|-----------|------|--------|
| **Correlation ID** | `src/agents/bridge/victoria_server.py` | ✅ Реализовано |
| **Кэш в LocalAIRouter** | `knowledge_os/app/local_router.py` | ✅ Реализовано |
| **Уточняющие вопросы** | `src/agents/bridge/victoria_server.py` | ✅ Реализовано |

**Уточнения по реализации:**

- **TaskResponse** содержит поля: `status`, `output`, `knowledge`, `correlation_id`. Поля `task_id`, `status_url`, `message`, `estimated_time` есть только в **ответе 202** (async_mode), не в модели TaskResponse.
- **Методы `get_cache_stats()` и `_get_average_entry_age()`** в LocalAIRouter **не реализованы** — доступны счётчики `_prompt_cache_hits`, `_prompt_cache_misses` и размер кэша; при необходимости эндпоинт метрик можно добавить отдельно.
- **Исправление бага:** поправлен отступ блока под `if best:` (присвоение `self.planner.model`, `self.executor.model` и лог), а не вызов несуществующего `best["model_info"]`.

Подробная полная версия документации: **`docs/IMPROVEMENTS_IMPLEMENTED_FULL.md`**.

---

## Обзор реализованных улучшений

Внедрены три ключевых улучшения в архитектуру Victoria Agent:

1. **Correlation ID** — сквозная идентификация запросов через заголовки
2. **Кэш в LocalAIRouter** — ускорение повторяющихся запросов с сохранением полного ответа (result, routing_source)
3. **Уточняющие вопросы** — предотвращение ошибок при неоднозначных задачах

---

## 1. Correlation ID — трассировка запросов

### Реализация

- **Файл:** `src/agents/bridge/victoria_server.py`
- Эндпоинт `POST /run` принимает **`body: TaskRequest`** и **`request: Request`** (порядок важен для FastAPI).
- Correlation ID: из заголовка **`X-Correlation-ID`** или **`str(uuid.uuid4())`** при отсутствии.

```python
@app.post("/run", response_model=TaskResponse)
async def run_task(
    body: TaskRequest,
    request: Request,
    async_mode: bool = Query(False),
):
    correlation_id = (request.headers.get("X-Correlation-ID") or "").strip() or str(uuid.uuid4())
    # ... передаётся во все ответы и в _run_task_store
```

### Где передаётся

- **TaskResponse** — поле `correlation_id: Optional[str] = None`
- **Ответ 202** (async_mode) — в `content["correlation_id"]`
- **GET /run/status/{task_id}** — в теле ответа `correlation_id`
- **knowledge.metadata** — при успешном выполнении добавляется `correlation_id`
- В логах используется короткий префикс: `correlation_id[:8]`

### Использование (клиент)

```python
import requests

# Своим ID
headers = {"X-Correlation-ID": "my-trace-123"}
r = requests.post("http://localhost:8010/run", json={"goal": "..."}, headers=headers)

# Или без заголовка — сервер сгенерирует UUID
r = requests.post("http://localhost:8010/run", json={"goal": "..."})
correlation_id = r.json().get("correlation_id")
```

### Пример ответа (успешное выполнение)

```json
{
  "status": "success",
  "output": "...",
  "knowledge": { "metadata": { "model_used": "...", "correlation_id": "..." } },
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Пример ответа 202 (фоновая задача)

```json
{
  "task_id": "...",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_url": "/run/status/{task_id}",
  "message": "Задача принята, выполняется в фоне. Опрашивайте status_url до status=completed."
}
```

---

## 2. Кэш в LocalAIRouter

### Реализация

- **Файл:** `knowledge_os/app/local_router.py`
- Кэш хранит **кортеж** `(result, routing_source)` — как возвращает `run_local_llm`.
- Ключ: `hashlib.sha256(f"{prompt}|{category or ''}|{model or ''}".encode()).hexdigest()[:32]`
- Кэшируются только запросы с `len(prompt) <= 1000` и без `images`; в кэш пишутся только ответы с `len(result) < 5000`.

```python
# В __init__
self._prompt_cache: Dict[str, Tuple[str, str]] = {}
self._prompt_cache_meta: Dict[str, float] = {}
self._prompt_cache_max = 500
self._prompt_cache_ttl = 1800  # 30 мин
self._prompt_cache_hits = 0
self._prompt_cache_misses = 0
```

### Логика вытеснения (LRU)

- **`_evict_prompt_cache_if_needed()`** вызывается перед добавлением новой записи.
- Сначала удаляются записи с истёкшим TTL.
- Если после этого размер >= `_prompt_cache_max`, удаляются самые старые по `_prompt_cache_meta` (по timestamp), пока размер не станет меньше лимита.

### Статистика

- **`_prompt_cache_hits`** — число попаданий в кэш
- **`_prompt_cache_misses`** — число промахов
- Глобальной функции **`get_router()`** в проекте нет; экземпляр `LocalAIRouter` создаётся в местах использования (например, в ai_core). Для мониторинга нужно передавать/получать этот экземпляр (например, через app.state или фабрику).

### Метрики (если добавить эндпоинт)

Если где-то доступен экземпляр роутера:

```python
total = router._prompt_cache_hits + router._prompt_cache_misses
hit_rate = (router._prompt_cache_hits / max(total, 1)) * 100
# size = len(router._prompt_cache), max_size = router._prompt_cache_max, ttl = router._prompt_cache_ttl
```

---

## 3. Уточняющие вопросы

### Реализация

- **Файл:** `src/agents/bridge/victoria_server.py`
- Три функции: **`_check_ambiguity`**, **`_generate_clarification_questions`**, **`_understand_goal_with_clarification`**.

### `_check_ambiguity(goal, category, restated)` → bool

Синхронная эвристика. Возвращает `True`, если **сумма индикаторов >= 2**:

- `len(goal.split()) < 3`
- местоимения: «он», «она», «оно», «они», «это», «то»
- неопределённые слова: «что-то», «какой-то», «кое-что», «где-то»
- `category == "multi_step"` и `len(goal) < 50`
- `goal.count("но") > 1` или «однако» в goal

### `_generate_clarification_questions(agent, goal, restated)` → List[str]

- Вызов **`agent.planner.ask(prompt, raw_response=True)`** с промптом, требующим JSON `{"questions": ["...?", ...]}`.
- Парсинг JSON из ответа (поиск `{...}` в строке); fallback — строки, заканчивающиеся на `?`.
- До 3 вопросов, длина каждого до 200 символов.
- При ошибке возвращаются дефолтные вопросы (например: «Можете уточнить, что именно нужно сделать?» и т.д.).

### `_understand_goal_with_clarification(agent, goal)` → dict

- Вызывает **`agent.understand_goal(goal)`** → `{restated, category, first_step}`.
- Если **`_check_ambiguity(goal, category, restated)`** → True: генерирует вопросы и возвращает:
  - `needs_clarification: True`
  - `clarification_questions`: список вопросов
  - `original_goal`, `restated`, `category`, `first_step`
- Иначе возвращает:
  - `needs_clarification: False`
  - `restated`, `category`, `first_step`

### Интеграция в run_task

- После проверки **async_mode** и до **use_enhanced**:
  1. `understanding = await _understand_goal_with_clarification(agent, body.goal)`
  2. Если `understanding.get("needs_clarification")` — ответ **JSONResponse 200** с:
     - `status: "needs_clarification"`
     - `correlation_id`
     - **`clarification_questions`** (не `questions`)
     - `original_goal`
     - **`suggested_restatement`** (переформулировка)
  3. Иначе `restated_goal = understanding.get("restated") or body.goal` и дальше:
     - **use_enhanced**: `enhanced.solve(restated_goal, ...)`
     - стандартный режим: `agent.run(restated_goal, ...)`

### Пример ответа при неоднозначной задаче

```json
{
  "status": "needs_clarification",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "clarification_questions": [
    "Какой язык программирования использовать?",
    "Какие требования к результату?"
  ],
  "original_goal": "Сделай сортировку",
  "suggested_restatement": "Реализовать алгоритм сортировки данных"
}
```

Клиенту нужно смотреть поле **`clarification_questions`** (не `questions`).

---

## 4. Исправление бага в _ensure_best_available_models

- **Файл:** `src/agents/bridge/victoria_server.py`
- Исправлен отступ блока **`if best:`** — код внутри блока выровнен по одному уровню с `if best:`.

---

## Обратная совместимость

- Старые клиенты без заголовка **X-Correlation-ID** получают автоматически сгенерированный UUID в ответе.
- Кэш в LocalAIRouter не меняет контракт API; возвращается тот же кортеж `(result, routing_source)`.
- Уточняющие вопросы срабатывают только при срабатывании эвристик; в ответе используется стандартный **200** с **`status: "needs_clarification"`** и **`clarification_questions`**.

---

## Чеклист внедрения

- [x] Correlation ID в TaskResponse и во всех ответах /run и /run/status
- [x] Заголовок X-Correlation-ID обрабатывается в run_task
- [x] Кэш в LocalAIRouter с LRU (сначала TTL, затем самые старые)
- [x] Кэшируется кортеж (result, routing_source)
- [x] _check_ambiguity(goal, category, restated) с реализованными эвристиками
- [x] _generate_clarification_questions через agent.planner.ask
- [x] Интеграция в run_task: при needs_clarification — JSONResponse с clarification_questions и suggested_restatement
- [x] restated_goal используется в enhanced.solve и agent.run
- [x] Исправлен отступ в _ensure_best_available_models

---

## Рекомендации по эксплуатации

- **Кэш:** при необходимости можно изменить `_prompt_cache_max` и `_prompt_cache_ttl` в `LocalAIRouter.__init__`.
- **Поиск по логам:** по префиксу correlation_id в логах: `correlation_id[:8]`.
- **Порог неоднозначности:** при желании можно заменить жёсткое `>= 2` в `_check_ambiguity` на взвешенную сумму с порогом (как в рекомендациях в ARCHITECTURE_IMPROVEMENTS_ANALYSIS.md).

---

*Документ приведён в соответствие с реализованным кодом.*  
*Файлы: `src/agents/bridge/victoria_server.py`, `knowledge_os/app/local_router.py`.*
