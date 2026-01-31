# Почему semantic_ai_cache была пустой

## Кратко

Данные в `semantic_ai_cache` появляются только когда **тот же экземпляр БД** используется и для записи кэша (semantic_cache/ai_core), и для чтения метрик (дашборд, SLA). Сейчас **БД только локальная (Mac Studio)** — удалённый дефолт убран.

## Причины отсутствия данных

### 1. **Разные базы данных (исправлено)**

- **Дашборд и SLA** читают из БД, заданной `DATABASE_URL` (например `postgresql://admin:secret@knowledge_postgres:5432/knowledge_os` в Docker на Mac Studio).
- **semantic_cache** по умолчанию использовал удалённый хост `185.177.216.15`; теперь дефолт — только локальная БД (DATABASE_URL или localhost).
- Итог раньше: запись могла идти в другую БД, дашборд смотрел в локальную → таблица в нужной БД пустая.

**Что сделано:** в `semantic_cache.py` дефолты переведены на локальную БД (DATABASE_URL или `localhost:5432/knowledge_os`). В `ai_core.py` в `SemanticAICache` передаётся `db_url=os.getenv("DATABASE_URL")`. Кэш и дашборд используют одну локальную БД.

### 2. **Запись только из ai_core**

В `semantic_ai_cache` пишут только те пути, где вызывается `cache.save_to_cache(...)`:

- **knowledge_os/app/ai_core.py** — при ответах после проверки кэша, при локальном/гибридном ответе, при одобрении кода Victoria, при сжатии контекста и т.д. (если используется `run_smart_agent_async`).
- **Victoria** вызывает ai_core при делегировании; свой `_save_to_cache` пишет только в память, не в БД.

Если запросы обрабатываются без ai_core (например только Victoria без делегирования в ai_core) или ai_core не импортируется в окружении — записей в таблицу не будет.

### 3. **Эмбеддинги (Ollama)**

`save_to_cache` в semantic_cache перед записью вызывает `get_embedding(query)` (Ollama: `OLLAMA_EMBED_URL`, модель `nomic-embed-text`). Если Ollama недоступен или эмбеддинг не получен — функция выходит без INSERT. Нужны работающий Ollama и модель эмбеддингов.

### 4. **Таблица и миграции**

Таблица создаётся миграциями:

- `knowledge_os/db/migrations/add_semantic_cache.sql`
- `knowledge_os/db/migrations/add_routing_metrics_to_cache.sql` (routing_source, performance_score, tokens_saved)

Если миграции не применены к той БД, которую использует приложение, таблицы не будет или не будет нужных колонок — запись может падать или не выполняться.

## Что проверить

1. **Одна БД для всего:** в окружении, где крутятся Victoria/ai_core и дашборд, задан один и тот же `DATABASE_URL` (и он передаётся в SemanticAICache, что уже сделано в коде).
2. **Обработка через ai_core:** часть запросов идёт через `run_smart_agent_async` (например при делегировании из Victoria), чтобы срабатывали вызовы `cache.save_to_cache`.
3. **Ollama:** запущен и доступен по `OLLAMA_EMBED_URL`, есть модель для эмбеддингов (например `nomic-embed-text`).
4. **Миграции:** к этой БД применены миграции с `semantic_ai_cache` и расширением под routing/tokens_saved.

После этого записи в `semantic_ai_cache` должны появляться в той же БД, которую читает дашборд, и метрики Cache Hit Rate / Token Savings смогут стать ненулевыми.
