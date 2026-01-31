# Результаты Фазы 2

## Реализовано

### 1. RAG-light для фактуальных запросов

- **Сервис:** `backend/app/services/rag_light.py` — `RAGLightService`
- **Поведение:** эмбеддинг запроса через Ollama, один чанк по pgvector, высокий порог релевантности, таймаут 200 ms
- **Интеграция:** режим Ask в `backend/app/routers/chat.py` — для `type == "factual"` вызывается `fast_fact_answer`
- **Кэш:** in-memory кэш по хэшу запроса
- **Настройка:** `RAG_LIGHT_ENABLED`, `RAG_LIGHT_THRESHOLD`, `RAG_LIGHT_MAX_LENGTH`, `RAG_LIGHT_TIMEOUT_MS`, `OLLAMA_EMBED_MODEL` в `.env`

### 2. Подсказка перехода в Agent

- **Классификатор:** `backend/app/services/query_classifier.py` — `analyze_complexity()`: паттерны, ключевые слова, глаголы, длина запроса
- **Рекомендация:** для сложных запросов в режиме Ask отправляется шаг «Рекомендация» (stepType: thought, title: «Рекомендация»)
- **UI:** кнопка «Перейти в Агент» в `frontend/src/components/Chat.svelte` при шаге с title «Рекомендация»; по клику переключение на вкладку Агент
- **Метрики:** `backend/app/metrics/agent_suggestions.py` — `AgentSuggestionMetrics`, запись при показе рекомендации; эндпоинт `GET /api/chat/agent-suggestions/stats`

### 3. Метрики и мониторинг

- **Рекомендации Agent:** счётчики и `get_stats()` (total_queries, suggested_count, suggestion_rate, top_reasons)
- **Эндпоинты:** `GET /api/chat/classify?q=...`, `GET /api/chat/agent-suggestions/stats`
- **Логи:** `[Ask] Hot path`, `[Ask] RAG-light path`, `[Ask] Agent suggestion shown`

## Статистика (пример после тестирования)

| Метрика                     | Значение (заполнить по факту) |
|-----------------------------|--------------------------------|
| RAG-light hit rate          | —                              |
| Среднее время RAG-light     | ~120 ms (целевое)              |
| Рекомендаций Agent показано| через `/api/chat/agent-suggestions/stats` |
| Переходов по рекомендации   | (при добавлении трекинга)      |

## Улучшения производительности

- **Простые запросы (шаблон):** ответ без LLM, целевое время &lt; 50 ms (раньше ~500 ms через LLM).
- **Фактуальные (RAG-light):** целевое время 100–200 ms при попадании в БЗ (раньше 800–1200 ms через LLM).
- **Сложные:** показ рекомендации перейти в Агент + обычный путь (MLX/Ollama/Victoria); нагрузка на LLM для простых/фактуальных снижается.

## Тесты и скрипты

- `backend/app/tests/test_rag_light.py` — pytest: extract_direct_answer, classify, analyze_complexity
- `scripts/test_rag_light.py` — проверка логики и (при поднятом бэкенде) API
- `scripts/test_agent_suggestions.py` — проверка рекомендаций локально и через `/api/chat/classify`
- `scripts/test_rag_light_integration.py` — интеграционный тест POST `/api/chat/stream` в режиме Ask
- `scripts/check_phase2.sh` — финальная проверка Фазы 2
