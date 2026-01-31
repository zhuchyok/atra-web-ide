# Оптимизация latency RAG (Фаза 4.1)

**Цель:** P95 < 300ms для режима Ask.

## Цепочка Ask режима

```
шаблоны (мгновенно) → RAG-light (embeddings + search) → MLX/Ollama (LLM fallback) → Victoria
```

- **RAG-light:** эмбеддинги (Ollama → fallback), векторный поиск, извлечение ответа
- **MLX** (порт 11435): LLM-генерация при fallback RAG, приоритет над Ollama на Apple Silicon
- **Ollama** (порт 11434): эмбеддинги (nomic-embed-text), LLM если MLX недоступен
- **Victoria:** сложные запросы, планирование

## Порядок эмбеддингов (latency-оптимизированный)

1. **Батч-кэш** (если `EMBEDDING_BATCH_ENABLED=true`) — Ollama + кэш
2. **Ollama** — быстро, без загрузки Python-модели
3. **Fallback** (sentence-transformers) — медленно, только если Ollama недоступна

*Раньше fallback вызывался до Ollama, из‑за чего P95 уходил в 5+ сек.*

## Результаты бенчмарка

| Конфигурация | P50 | P95 | Avg embedding |
|--------------|-----|-----|---------------|
| Ollama + `EMBEDDING_FALLBACK_ENABLED=false` | 78 ms | **112 ms** ✅ | 41 ms |
| Fallback sentence-transformers | 75 ms | 5622 ms ❌ | 594 ms |

**При Ollama:** P95 < 300ms достигается. Fallback — только при недоступности Ollama.

## Причины

1. **Fallback до Ollama** — локальная модель вызывалась первой и блокировала быстрый путь.
2. **Холодный старт** — sentence-transformers грузит модель ~5–6 сек при первом запросе.
3. **Ollama и MLX** — Ollama быстрее для эмбеддингов; MLX — для LLM (generation).

## Рекомендации

1. **Запустить Ollama для эмбеддингов:**
   ```bash
   ollama pull nomic-embed-text
   curl -s http://localhost:11434/api/tags
   ```

2. **MLX для LLM (Ask fallback):** при недоступности RAG ответа используется MLX → Ollama. MLX на Apple Silicon обычно быстрее.
   ```bash
   # MLX API Server (порт 11435)
   scripts/start_mlx_api_server.sh
   ```

3. **Отключить fallback** (если Ollama доступна) — для стабильного P95 < 300ms:
   ```bash
   export EMBEDDING_FALLBACK_ENABLED=false
   # или в .env
   EMBEDDING_FALLBACK_ENABLED=false
   ```

4. **Кэш эмбеддингов** (при реализации):
   - Кэшировать частые запросы в Redis/памяти
   - Hit rate > 80% сильно снизит P95

5. **Прогрев при старте:** 5–10 типичных запросов на эмбеддинги

## Мониторинг кэша

```bash
# API (требует запущенный backend)
curl http://localhost:8080/api/cache/stats

# Скрипт
python scripts/monitor_cache_performance.py
```

## Команды

```bash
# Бенчмарк latency
python scripts/benchmark_latency.py

# API (после запуска бенчмарка)
curl http://localhost:8080/api/latency/benchmark

# Дашборд latency
python scripts/create_latency_dashboard.py
# Открыть: latency_dashboard.html
```

## Интеграция

- **CI/CD:** `quality-validation.yml` — шаг latency benchmark (--no-fail)
- **Quality pipeline:** `run_quality_pipeline.sh` — бенчмарк + дашборд
- **Load test:** `run_load_test.sh` — вывод P95 из `/api/latency/benchmark`
- **Backend:** прогрев embeddings при старте (`RAG_EMBEDDING_WARMUP_ENABLED=true`)

## Дополнительные оптимизации (Ollama + MLX)

1. **pgvector HNSW индекс** — ускорение векторного поиска:
   ```bash
   # Через Python (рекомендуется)
   PYTHONPATH=backend:. python scripts/apply_hnsw_index.py
   # Или через psql
   psql $DATABASE_URL -f knowledge_os/db/migrations/add_hnsw_index_knowledge_nodes.sql
   # Проверка: psql $DATABASE_URL -f scripts/check_pgvector_index.sql
   ```

2. **RAG Context Cache** — кэш результатов поиска (Redis + локальный), −150ms при хите.

3. **Unified Embedding Provider** — переиспользование эмбеддингов в рамках запроса.

4. **Redis** — см. `docs/REDIS_OPTIMIZATION.md`.

## Файлы

- `backend/app/services/latency_tracer.py` — трассировка по этапам
- `scripts/benchmark_latency.py` — бенчмарк
- `scripts/create_latency_dashboard.py` — дашборд
- `backend/app/routers/latency.py` — API
- `latency_benchmark.json`, `latency_dashboard.html` — результаты
- `backend/app/services/rag_context_cache.py` — RAG Context Cache
- `backend/app/services/unified_embedding_provider.py` — Unified Embedding Provider
