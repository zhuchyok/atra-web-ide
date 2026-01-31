# Фаза 2: RAG-light и оптимизация (7 дней)

**Дата:** 2026-01-30  
**Ссылка:** основной документ — `docs/CHAT_MODES_ARCHITECTURE_ANALYSIS.md`.

---

## Цели Фазы 2

1. **RAG-light** — фактуальные запросы в Ask отвечать из БЗ за &lt;200 ms.
2. **Подсказка Agent** — для сложных запросов показывать рекомендацию перейти в режим Агент, но давать быстрый ответ.
3. **Кэш планов** — повторные запросы планов из кэша (локальный + опционально Redis).
4. **Метрики** — распределение запросов по путям и время ответа.

---

## День 1–2: RAG-light для фактуальных запросов

### Цель

Ускорить ответы на фактуальные вопросы с использованием БЗ (1 чанк, высокий порог релевантности).

### Компоненты

- **`backend/app/services/rag_light.py`** — `RAGLightService`:
  - `fast_fact_answer(query: str) -> Optional[str]`
  - Поиск по вектору: 1 чанк, порог 0.75, таймаут 200 ms.
  - Если чанк найден — краткий ответ из контекста; иначе `None` (идём в MLX/Ollama).
- **Интеграция в `sse_generator`** (режим Ask, `classification["type"] == "factual"`):
  - Вызов `rag_light_service.fast_fact_answer(message.content)`.
  - При непустом ответе — шаг «Быстрый ответ», «Нашёл в базе знаний», чанки, `end`.
  - Иначе — текущий путь MLX → Ollama → Victoria.

### Конфигурация

```env
RAG_LIGHT_ENABLED=true
RAG_LIGHT_CHUNK_LIMIT=1
RAG_LIGHT_THRESHOLD=0.75
RAG_LIGHT_MAX_RESPONSE_LENGTH=150
RAG_LIGHT_TIMEOUT_MS=200
```

### Зависимости

- Эмбеддинг-провайдер (Ollama/MLX или Knowledge OS).
- Векторный поиск по БЗ (pgvector в Knowledge OS или через Victoria).

### Реализовано (RAG-light)

- **`backend/app/services/rag_light.py`** — `RAGLightService`: эмбеддинг через Ollama `/api/embeddings` (модель `OLLAMA_EMBED_MODEL`, по умолчанию nomic-embed-text), поиск 1 чанка через `knowledge_os.search_knowledge_by_vector`, `extract_direct_answer`, `fast_fact_answer` с таймаутом и кэшем.
- **`backend/app/services/knowledge_os.py`** — добавлен `search_knowledge_by_vector(embedding, limit, threshold)` (pgvector, таблица `knowledge_nodes` с колонкой `embedding`).
- **`backend/app/config.py`** — добавлены `rag_light_enabled`, `rag_light_threshold`, `rag_light_max_length`, `rag_light_timeout_ms`, `ollama_embed_model`.
- **`backend/app/routers/chat.py`** — в режиме Ask при `classification["type"] == "factual"` вызывается RAG-light; при успехе — шаг «Найдено в БЗ» и ответ; при неудаче или таймауте — fallback MLX → Ollama → Victoria.
- **`scripts/test_rag_light.py`** — тест `extract_direct_answer` и (при доступном бэкенде) фактуального запроса через API.

**Проверка:** В режиме Чат (Ask) отправить фактуальный вопрос (например «сколько стоит подписка?»). Если в БЗ есть релевантный чанк с эмбеддингом — ответ пойдёт по RAG-light; иначе — MLX/Ollama. Логи: `[Ask] RAG-light path: factual query -> answer from KB` или `RAG-light success: ...`.

---

## День 3–4: Подсказка перехода в Agent

### Цель

Для сложных запросов показывать рекомендацию «перейти в режим Агент», но продолжать давать быстрый ответ через MLX/Ollama.

### Компоненты

- **Расширение `query_classifier.py`**:
  - Функция `analyze_complexity(query) -> Dict` (или метод в классе):
    - Для `type == "complex"` проверять ключевые слова: проанализируй, сравни, оцени, рекомендуй, план, стратегия, оптимизируй и т.д.
    - Возвращать `suggest_agent: bool`, `complexity_score: float`.
- **В `sse_generator`** (режим Ask, `classification["type"] == "complex"`):
  - Если `suggest_agent` — отправить шаг SSE «Рекомендация» с текстом: «Этот запрос требует глубокого анализа. Для полного ответа перейдите в режим „Агент“.»
  - Затем продолжить обычный путь (MLX → Ollama → Victoria).

### Конфигурация

```env
AGENT_SUGGESTION_ENABLED=true
AGENT_SUGGESTION_MIN_COMPLEXITY=0.6
AGENT_SUGGESTION_KEYWORDS=проанализируй,сравни,оцени,рекомендуй,план,стратегия,оптимизируй
AGENT_SUGGESTION_DELAY_MS=500
```

---

## День 5–6: Кэш планов

### Цель

Повторные запросы планов с той же целью возвращать из кэша без вызова Victoria.

### Компоненты

- **`backend/app/services/plan_cache.py`** — `PlanCache`:
  - Ключ: хэш нормализованной цели (+ эксперт при наличии). TTL: локальный 30 мин, Redis (если есть) 1 ч.
  - `get(goal, expert=None) -> Optional[Dict]`, `set(goal, plan, expert=None, ttl=3600)`.
- **Интеграция:** в обработчике `POST /api/chat/plan` (или в Victoria-клиенте):
  - Перед вызовом Victoria — проверка кэша.
  - При попадании — возврат плана из кэша (можно пометить `_cached: true`).
  - После успешной генерации — сохранение в кэш (например, если время генерации &gt; 1 с).

### Конфигурация

```env
PLAN_CACHE_ENABLED=true
PLAN_CACHE_TTL=1800
PLAN_CACHE_REDIS_TTL=3600
PLAN_CACHE_MIN_GENERATION_TIME=1.0
```

---

## День 7: Мониторинг и метрики

### Цель

Отслеживать использование путей (template / rag_light / llm_direct / cached) и время ответа для оптимизации.

### Компоненты

- **`backend/app/services/path_metrics.py`** (или `metrics/path_metrics.py`):
  - Счётчики по режиму (ask / agent / plan) и по пути (template / rag_light / rag_full / llm_direct / cached).
  - Время ответа по путям (список или скользящее среднее).
  - `track(mode, path, duration_ms)`, `get_summary() -> Dict`.
- **Эндпоинт:** `GET /api/chat/metrics` или `GET /api/metrics/paths`:
  - Возврат: `summary` (распределение, среднее/p95 времени), `timestamp`.

### Конфигурация

```env
TRACK_PATHS=true
LOG_PATH_DECISIONS=true
METRICS_FLUSH_INTERVAL=100
```

---

## Конфигурация Фазы 2 (сводка)

```env
# RAG-light
RAG_LIGHT_ENABLED=true
RAG_LIGHT_CHUNK_LIMIT=1
RAG_LIGHT_THRESHOLD=0.75
RAG_LIGHT_TIMEOUT_MS=200

# Подсказка Agent
AGENT_SUGGESTION_ENABLED=true
AGENT_SUGGESTION_MIN_COMPLEXITY=0.6

# Кэш планов
PLAN_CACHE_ENABLED=true
PLAN_CACHE_TTL=1800
PLAN_CACHE_MIN_GENERATION_TIME=1.0

# Метрики
TRACK_PATHS=true
```

---

## Критерии успеха Фазы 2

| Критерий | Цель |
|----------|------|
| **Скорость** | Фактуальные запросы в Ask &lt;200 ms при RAG-light hit |
| **Качество** | RAG-light даёт точные ответы по фактам из БЗ |
| **UX** | Рекомендация «перейти в Агент» не мешает, быстрый ответ приходит |
| **Эффективность** | Повторные планы из кэша без вызова Victoria |
| **Мониторинг** | Видно распределение по путям и время по путям |

---

## Чек-лист начала Фазы 2

### Перед началом

- [ ] Фаза 1 полностью работает (тесты + веб).
- [ ] Зафиксировать базовые метрики скорости (опционально).
- [ ] Протестировать RAG/поиск по БЗ на тестовых данных.

### День 1–2 (RAG-light)

- [ ] Создать `RAGLightService` (поиск 1 чанка, порог, таймаут).
- [ ] Протестировать поиск одного чанка отдельно.
- [ ] Интегрировать в `sse_generator` для factual в Ask.
- [ ] Добавить конфигурацию и переменные окружения.

### День 3–4 (Подсказка Agent)

- [ ] Расширить классификатор (анализ сложности, ключевые слова).
- [ ] Добавить шаг «Рекомендация» в SSE для complex с `suggest_agent`.
- [ ] Проверить UX (рекомендация не мешает чтению ответа).

### День 5–6 (Кэш планов)

- [ ] Реализовать `PlanCache` (локальный TTL, опционально Redis).
- [ ] Интегрировать в обработку планов (backend или Victoria-клиент).
- [ ] Протестировать повторные запросы планов.

### День 7 (Мониторинг)

- [ ] Реализовать сбор метрик по путям.
- [ ] Добавить эндпоинт для просмотра метрик.
- [ ] При необходимости — алерты на замедление.

---

## Действия сейчас

1. **Документация** — обновлена: `docs/CHAT_MODES_ARCHITECTURE_ANALYSIS.md` (Фаза 1: ГОТОВО, Фаза 2: план) и `docs/PHASE2_PLAN.md` (детальный план).
2. **Старт реализации** — начать с RAG-light (день 1–2): максимальный эффект при минимальных рисках.
3. **Тесты** — перед RAG-light замерить текущее время ответа на фактуальные запросы для сравнения.
