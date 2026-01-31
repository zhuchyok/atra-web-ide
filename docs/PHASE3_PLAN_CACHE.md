# Фаза 3: Кэш планов (День 1–2)

## Реализовано

### PlanCacheService (`backend/app/services/plan_cache.py`)

- **Локальный кэш:** TTLCache (cachetools), maxsize и ttl из конфига.
- **Опционально Redis:** при `PLAN_CACHE_REDIS_ENABLED=true` и доступном Redis — второй уровень кэша (pickle).
- **Ключ:** `sha256(normalized_goal + ":" + project_context)[:16]`, префикс `plan:`.
- **Методы:** `get(goal, project_context)`, `set(goal, plan, project_context, ttl)`, `clear(goal?, project_context?)`, `stats()`.

### Конфигурация (`backend/app/config.py`)

- `PLAN_CACHE_ENABLED` — включить кэш (по умолчанию true).
- `PLAN_CACHE_TTL` — TTL в секундах (по умолчанию 3600).
- `PLAN_CACHE_REDIS_ENABLED` — использовать Redis (по умолчанию false).
- `PLAN_CACHE_MAXSIZE` — размер in-memory кэша (по умолчанию 100).
- `PLAN_CACHE_MIN_GEN_TIME` — кэшировать только если генерация плана заняла не меньше N секунд (по умолчанию 2.0).
- `REDIS_URL` — URL Redis при включённом Redis.

### Интеграция

- **Режим Plan (SSE):** в `sse_generator` при `mode == "plan"` сначала проверяется кэш; при попадании стримится шаг «План из кэша» и текст плана; при промахе вызывается Victoria, время замеряется, при успехе и `gen_time >= plan_cache_min_gen_time` план сохраняется в кэш.
- **POST /api/chat/plan:** то же: проверка кэша → при промахе вызов Victoria → при успехе и достаточном времени генерации — сохранение в кэш.

### Эндпоинты (`/api/plan-cache`)

- `GET /api/plan-cache/stats` — статистика (local_cache_size, redis_cache_size при использовании Redis).
- `POST /api/plan-cache/clear?goal=...&project_context=...` — очистка по ключу или всего кэша (без параметров).

### Зависимости

- `cachetools>=5.3.0` — TTLCache.
- `redis>=5.0.0` — опционально для второго уровня кэша.

### Тесты

- `backend/app/tests/test_plan_cache.py`: set/get, ключ с project_context, clear, stats, отключённый кэш (maxsize=0).

## Использование

1. Включить кэш: `PLAN_CACHE_ENABLED=true` (по умолчанию уже true).
2. Повторный запрос плана по тому же goal и project_context вернёт результат из кэша (шаг «План из кэша» в SSE или быстрый ответ в POST /plan).
3. Планы кэшируются только если генерация заняла не меньше `PLAN_CACHE_MIN_GEN_TIME` секунд.

## Дальше (Фаза 3)

- День 3–4: батчинг эмбеддингов, предзагрузка частых запросов RAG-light.
- День 5: Prometheus-метрики, эндпоинт /metrics.
- День 6: A/B-тесты параметров.
- День 7: стресс-тесты, документация по нагрузке.
