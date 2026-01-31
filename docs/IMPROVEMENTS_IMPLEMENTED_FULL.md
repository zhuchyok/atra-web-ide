# Документация по внедрённым улучшениям — полная версия

## Обзор внедрённых улучшений

**Статус:** ✅ Внедрено в коде  
**Версия системы:** Victoria Agent 2.1+

Внедрены три ключевых улучшения:

| Улучшение | Статус | Эффект |
|-----------|--------|--------|
| **Correlation ID** | ✅ Работает | Трассировка запросов |
| **Кэш в LocalAIRouter** | ✅ Работает | Ускорение повторяющихся запросов (ожидаемо 30–70%) |
| **Уточняющие вопросы** | ✅ Работает | Снижение ошибок при неоднозначных задачах |

---

## 1. Correlation ID — трассировка запросов

### Как это работает

- **Заголовок:** `X-Correlation-ID` (опциональный)
- **Автогенерация:** при отсутствии заголовка — `str(uuid.uuid4())`
- **Передача:** во всех ответах (TaskResponse, 202, GET /run/status), в `knowledge.metadata`
- **Логирование:** префикс `correlation_id[:8]` в логах

### Реализация в коде

**Файл:** `src/agents/bridge/victoria_server.py`

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

**TaskResponse** (реальные поля в коде):

```python
class TaskResponse(BaseModel):
    status: str
    output: Any
    knowledge: Optional[dict] = None
    correlation_id: Optional[str] = None
```

Поля `task_id`, `status_url`, `message`, `estimated_time` **не входят в TaskResponse** — они только в **ответе 202** (JSONResponse при async_mode).

### Примеры ответов

**Успешное выполнение (TaskResponse):**

```json
{
  "status": "success",
  "output": "...",
  "knowledge": { "metadata": { "model_used": "...", "correlation_id": "..." } },
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Фоновая задача (202, JSONResponse):**

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

### Реализация в коде

**Файл:** `knowledge_os/app/local_router.py`

- Кэш: `_prompt_cache` (key → `(result, routing_source)`), `_prompt_cache_meta` (key → timestamp)
- Параметры: `_prompt_cache_max = 500`, `_prompt_cache_ttl = 1800` (30 мин)
- Счётчики: `_prompt_cache_hits`, `_prompt_cache_misses`
- Ключ: `hashlib.sha256(f"{prompt}|{category or ''}|{model or ''}".encode()).hexdigest()[:32]`
- Кэшируются только: `len(prompt) <= 1000`, без `images`, результат `len(result) < 5000`

**Вытеснение:** `_evict_prompt_cache_if_needed()` — сначала удаляются записи с истёкшим TTL, затем при переполнении самые старые по timestamp (возможно несколько записей).

### Что не реализовано (рекомендуется добавить при необходимости)

- Методы **`get_cache_stats()`** и **`_get_average_entry_age()`** в LocalAIRouter **отсутствуют**. Для мониторинга можно использовать напрямую: `router._prompt_cache_hits`, `router._prompt_cache_misses`, `len(router._prompt_cache)`.
- Глобальной функции **`get_router()`** в проекте нет — экземпляр LocalAIRouter создаётся в местах использования (например, в ai_core). Эндпоинт вида `/router/cache/stats` потребует доступа к этому экземпляру (например, через app.state).

### Ограничения

- Не кэшируются промпты > 1000 символов
- Не кэшируются запросы с изображениями
- Не кэшируются результаты > 5000 символов

---

## 3. Уточняющие вопросы

### Реализация в коде

**Файл:** `src/agents/bridge/victoria_server.py`

- **`_check_ambiguity(goal, category, restated)`** — синхронная эвристика; возвращает `True`, если **сумма индикаторов >= 2**: длина < 3 слов, местоимения (он, она, это, то…), неопределённые слова (что-то, какой-то…), `category == "multi_step"` и `len(goal) < 50`, «но»/«однако».
- **`_generate_clarification_questions(agent, goal, restated)`** — вызов `agent.planner.ask(...)`, парсинг JSON `{"questions": [...]}`, до 3 вопросов, fallback-вопросы при ошибке.
- **`_understand_goal_with_clarification(agent, goal)`** — вызывает `agent.understand_goal(goal)`, затем при срабатывании `_check_ambiguity` генерирует вопросы и возвращает dict с `needs_clarification`, `clarification_questions`, `original_goal`, `restated`, `suggested_restatement` и т.д.

### Интеграция в run_task

После проверки async_mode, до use_enhanced:

1. `understanding = await _understand_goal_with_clarification(agent, body.goal)`
2. Если `understanding.get("needs_clarification")` — возвращается **JSONResponse 200** с полями: `status: "needs_clarification"`, `correlation_id`, **`clarification_questions`**, `original_goal`, **`suggested_restatement`** (не `restated` в этом ответе).
3. Иначе `restated_goal = understanding.get("restated") or body.goal` используется в `enhanced.solve(restated_goal, ...)` и `agent.run(restated_goal, ...)`.

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

Клиенту нужно использовать поле **`clarification_questions`** (не `questions`).

---

## 4. Исправление бага

**Файл:** `src/agents/bridge/victoria_server.py`, метод `_ensure_best_available_models`

**Было:** блок под `if best:` имел лишний отступ (строки с `env_model`, `merged`, `self.planner.model`, `self.executor.model`, `logger.info` были сдвинуты на один уровень глубже, чем нужно).

**Стало:** отступ исправлен — весь блок под `if best:` выровнен корректно. В коде нет обращения к `best["model_info"]`; исправлялись только отступы существующего кода.

---

## 5. Рекомендации по мониторингу и настройке

- **Кэш:** при необходимости изменить `_prompt_cache_max` и `_prompt_cache_ttl` в `LocalAIRouter.__init__`.
- **Метрики кэша:** при необходимости добавить эндпоинт, который по экземпляру роутера возвращает `_prompt_cache_hits`, `_prompt_cache_misses`, `len(_prompt_cache)`, hit_rate.
- **Эвристики неоднозначности:** при желании заменить жёсткое `>= 2` в `_check_ambiguity` на взвешенную сумму с порогом.

---

## 6. Обратная совместимость

- Старые клиенты без заголовка X-Correlation-ID получают автоматически сгенерированный UUID в ответе.
- Кэш в LocalAIRouter не меняет контракт API.
- Уточняющие вопросы возвращают 200 с `status: "needs_clarification"` и `clarification_questions` — клиент может обрабатывать этот случай отдельно.

---

## Заключение

Да, все три улучшения реализованы и работают в коде. Документ приведён в соответствие с реализацией; разделы про расширенные метрики и дашборды — рекомендации на будущее.

*Документ приведён в соответствие с кодом. Файлы: `src/agents/bridge/victoria_server.py`, `knowledge_os/app/local_router.py`.*
