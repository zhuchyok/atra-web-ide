# Nightly Learner — в atra-web-ide

Nightly Learner перенесён из atra в atra-web-ide и настроен на работу с общей БД.

## Что делает

- Обучает экспертов (knowledge_nodes, гипотезы)
- Обрабатывает дебаты (expert_discussions)
- Синхронизирует OKRs
- Пишет в `tasks`, `knowledge_nodes` — обновляет «БД: X ч назад» на дашборде

## Запуск

Сервис добавлен в `knowledge_os/docker-compose.yml`:

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_nightly
```

Или вместе со всем Knowledge OS:

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d
```

## Расписание

Цикл выполняется каждые **24 часа** (после завершения предыдущего + 24ч).

## Требования

- `knowledge_postgres` — PostgreSQL (из atra или knowledge_os)
- `knowledge_redis` — Redis (для distributed lock)
- Ollama/MLX на хосте (`host.docker.internal:11434`, `:11435`)

## Конфликт с atra

atra тоже определяет `knowledge_nightly`. Если оба проекта запущены, возможен конфликт контейнеров. Остановите atra: `cd atra && docker-compose stop knowledge_nightly`

## Миграция knowledge_nodes (2026-01-31)

Схема knowledge_nodes из atra backup не имела колонок `expert_consensus`, `source_ref`, `updated_at`. Миграция `add_knowledge_nodes_missing_columns.sql` добавлена и применяется при необходимости:

```bash
docker exec -i knowledge_postgres psql -U admin -d knowledge_os < knowledge_os/db/migrations/add_knowledge_nodes_missing_columns.sql
```

## Логи

```bash
docker logs -f knowledge_nightly
```
