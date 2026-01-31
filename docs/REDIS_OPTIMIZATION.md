# Оптимизация Redis для latency

Ollama (embeddings) + MLX (LLM) + RAG Context Cache: Redis ускоряет повторные запросы.

## Рекомендуемая конфигурация

```yaml
# Для кэша (RAG, планы) — без персистентности, максимум скорость
command:
  - redis-server
  - --save ""              # Отключаем RDB
  - --appendonly no        # Отключаем AOF
  - --maxmemory 1gb
  - --maxmemory-policy allkeys-lru
  - --activerehashing yes
```

## Knowledge OS Redis

Redis задаётся в `knowledge_os/docker-compose.yml` как `knowledge_redis`.  
Web IDE использует его через `REDIS_URL=redis://knowledge_redis:6379`.

Для оптимизации добавьте в `knowledge_os/docker-compose.yml` в секцию redis:

```yaml
knowledge_redis:
  command:
    - redis-server
    - --maxmemory-policy allkeys-lru
    - --activerehashing yes
```

## Метрики

- **RAG Context Cache hit** — экономия ~150ms (embedding + vector search)
- **Plan Cache hit** — экономия 2–10s (генерация плана)
- Мониторинг: `redis-cli INFO stats` — keyspace_hits, keyspace_misses
