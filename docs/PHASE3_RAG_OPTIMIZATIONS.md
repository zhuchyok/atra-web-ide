# Фаза 3, день 3–4: Оптимизации RAG-light

## Реализовано

### 1. EmbeddingBatchProcessor (`backend/app/services/embedding_batch.py`)

- Очередь запросов эмбеддингов, сбор в батчи по таймауту и размеру.
- Параллельные вызовы Ollama для батча (Ollama не поддерживает один батч — делаем `asyncio.gather` по одному запросу).
- In-memory кэш результатов по нормализованному тексту.
- Методы: `get_embedding(text)`, `clear_cache()`, `stats()`.

### 2. RAGLightPrefetch (`backend/app/services/rag_light_prefetch.py`)

- Загрузка частых запросов из JSON-файла или дефолтного списка.
- Предзагрузка эмбеддингов через `EmbeddingBatchProcessor.get_embedding` батчами по 20.
- Методы: `load_frequent_queries(max_queries)`, `is_prefetched(query)`, `get_stats()`.

### 3. EmbeddingFallback (`backend/app/services/embedding_fallback.py`)

- Локальная модель: опционально `sentence-transformers` (при установке).
- Keyword fallback: при отсутствии вектора — `knowledge_os.search_knowledge(query, limit=1)`.
- Гибридный поиск: `hybrid_search(vector_results, keyword_results, vector_weight)`.

### 4. Интеграция в RAGLightService

- `_init_optimizations()` — создаёт batch-процессор, prefetch, fallback по настройкам.
- `_get_embedding_optimized(query)` — порядок: батч-процессор → локальная модель → `get_embedding` (Ollama).
- `search_one_chunk` использует `_get_embedding_optimized`.
- В `_fast_fact_answer_impl` при отсутствии результата по вектору вызывается `keyword_search_fallback`.

### 5. Конфиг (`backend/app/config.py`)

- `embedding_batch_enabled`, `embedding_batch_size`, `embedding_batch_timeout_ms`
- `rag_light_prefetch_enabled`, `rag_light_prefetch_file`, `rag_light_prefetch_max_queries`
- `embedding_fallback_enabled`, `local_embedding_model`, `keyword_fallback_enabled`

По умолчанию батчинг и prefetch выключены (`false`), fallback включён (`true`).

### 6. Эндпоинты (`/api/rag-optimization`)

- `GET /api/rag-optimization/stats` — статистика batch, prefetch, fallback.
- `POST /api/rag-optimization/prefetch/reload` — перезапуск предзагрузки.
- `POST /api/rag-optimization/cache/clear` — очистка кэша эмбеддингов.

### 7. Тесты и скрипт

- `backend/app/tests/test_embedding_batch.py`
- `backend/app/tests/test_rag_light_prefetch.py`
- `backend/app/tests/test_embedding_fallback.py`
- `scripts/check_rag_optimizations.sh`
- `data/frequent_queries.json` — пример списка частых запросов.

## Включение оптимизаций

В `.env`:

```bash
# Батчинг (снижает нагрузку на Ollama при параллельных запросах)
EMBEDDING_BATCH_ENABLED=true
EMBEDDING_BATCH_SIZE=10
EMBEDDING_BATCH_TIMEOUT_MS=50

# Предзагрузка (прогрев кэша при старте)
RAG_LIGHT_PREFETCH_ENABLED=true
RAG_LIGHT_PREFETCH_FILE=data/frequent_queries.json
RAG_LIGHT_PREFETCH_MAX_QUERIES=50

# Fallback (keyword-поиск при недоступности Ollama)
EMBEDDING_FALLBACK_ENABLED=true
KEYWORD_FALLBACK_ENABLED=true
```

Локальная модель (опционально): `pip install sentence-transformers`, затем `LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2`.
