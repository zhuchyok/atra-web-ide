# Исправление схемы БД — 2026-01-31

## Проблема

На вкладках дашборда Intelligence Command Center возникали ошибки:
- **«column expert_consensus does not exist»** — вкладка «Иммунитет: Результаты Стресс-Тестов»
- Аналогичные ошибки на других вкладках из‑за отсутствующих колонок в `knowledge_nodes`

## Причина

Текущая схема `knowledge_nodes` отличается от ожидаемой в `init.sql`:
- Источник: atra backup / старая миграция
- Отсутствовали колонки: `expert_consensus`, `source_ref`, `updated_at`

## Решение

Создана и применена миграция `knowledge_os/db/migrations/add_knowledge_nodes_missing_columns.sql`:

| Колонка | Тип | Описание |
|---------|-----|----------|
| `expert_consensus` | JSONB DEFAULT '{}' | Результаты adversarial testing |
| `source_ref` | TEXT | Ссылка на файл/источник |
| `updated_at` | TIMESTAMPTZ | Время последнего обновления |

## Применение

```bash
docker exec -i knowledge_postgres psql -U admin -d knowledge_os < knowledge_os/db/migrations/add_knowledge_nodes_missing_columns.sql
```

## Проверка

После миграции дашборд должен работать на всех вкладках. Запрос Иммунитет:
```sql
SELECT content, expert_consensus->>'adversarial_attack' as attack, 
       metadata->>'survived' as survived, confidence_score
FROM knowledge_nodes 
WHERE metadata->>'adversarial_tested' = 'true'
ORDER BY created_at DESC LIMIT 15;
```
