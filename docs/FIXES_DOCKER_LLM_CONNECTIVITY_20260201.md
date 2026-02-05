# Исправления подключения к Ollama/MLX в Docker (01.02.2026)

## Причина проблем

**Корень проблемы:** в Docker `localhost` указывает на сам контейнер, а не на хост. Ollama и MLX API Server работают на хосте (Mac Studio). Для доступа из контейнера нужен `host.docker.internal`.

**Почему днём работало:**
- Возможно, часть запросов шла с хоста (дашборд, скрипты)
- Или Ollama/MLX были доступны по другому пути (проброс портов, другая сеть)

## Исправленные компоненты

### 1. semantic_cache.py — Embedding error (Ollama): All connection attempts failed

**Проблема:** `OLLAMA_EMBED_URL` по умолчанию `http://localhost:11434/api/embeddings`. В Docker Ollama недоступен по localhost.

**Решение:**
- Проверка `/.dockerenv` и `DOCKER_CONTAINER`
- В Docker используется `host.docker.internal` или `OLLAMA_BASE_URL` / `OLLAMA_API_URL`
- Добавлена переменная `OLLAMA_EMBED_URL` в `knowledge_os_worker`

### 2. model_memory_manager.py — Ошибка получения списка моделей

**Проблема:** `ModelMemoryManager(ollama_url="http://localhost:11434")` — жёстко задан localhost.

**Решение:**
- Функция `_default_ollama_url()` с определением Docker
- В Docker берётся `OLLAMA_BASE_URL` или `OLLAMA_API_URL`, иначе `host.docker.internal:11434`

### 3. local_router.py — Victoria не может сканировать модели

**Проблема:** `OLLAMA_API_URL` использовал только `OLLAMA_API_URL` и `SERVER_LLM_URL`, а Victoria задаёт только `OLLAMA_BASE_URL`.

**Решение:**
- Добавлена проверка `OLLAMA_BASE_URL` в цепочку fallback
- Определение Docker для дефолтного `host.docker.internal`

### 4. ai_core.py — Fallback Ollama при недоступности cursor-agent

**Проблема:** `for ollama_url in ["http://localhost:11434"]` — жёстко localhost.

**Решение:**
- Берётся `OLLAMA_BASE_URL` / `OLLAMA_API_URL` / `SERVER_LLM_URL` из env
- В Docker подставляется `host.docker.internal:11434`

### 5. docker-compose.yml — переменные окружения

**Добавлено:**
- `knowledge_os_worker`: `OLLAMA_EMBED_URL: http://host.docker.internal:11434/api/embeddings`
- `victoria-agent`: `OLLAMA_API_URL`, `SERVER_LLM_URL` (для local_router и model_memory_manager)

## Fallback «недоступности AI агента»

Сообщение *«Автоматическая обработка выполнена через fallback механизм из-за недоступности AI агента»* возникает, когда:
1. LLM возвращает ошибку (timeout, connection refused)
2. После 2+ попыток при LLM unavailable или 3+ при любой ошибке вызывается `task_rule_executor.execute_fallback`
3. Если rule_executor не находит шаблон — задача завершается с `deferred_to_human`

Причина: модели были недоступны из-за неверного URL (localhost вместо host.docker.internal). После правок соединение с Ollama/MLX из контейнеров должно восстанавливаться.

## Проверка после правок

```bash
# Перезапуск затронутых контейнеров
docker-compose -f knowledge_os/docker-compose.yml up -d --build knowledge_os_worker victoria-agent

# Логи worker — не должно быть Embedding error
docker logs knowledge_os_worker --tail 50

# Логи Victoria — не должно быть «Ошибка получения списка моделей»
docker logs victoria-agent --tail 50
```

## Условия для host.docker.internal

- **macOS/Windows (Docker Desktop):** работает без доп. настроек
- **Linux:** требуется `extra_hosts: - "host.docker.internal:host-gateway"` (есть у knowledge_os_worker)
