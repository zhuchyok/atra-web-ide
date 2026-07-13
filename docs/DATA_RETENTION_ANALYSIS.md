# Анализ очистки данных — что можно и что нельзя

## 🚨 Данные, которые **НЕ ТРОГАТЬ**

| Таблица/Источник             | Причина                                                                                 |
| ---------------------------- | --------------------------------------------------------------------------------------- |
| **knowledge_nodes**          | Ядро базы знаний. Удаление = потеря знаний.                                             |
| **experts**                  | Справочник экспертов.                                                                   |
| **domains**                  | Домены знаний.                                                                          |
| **tasks**                    | Задачи оркестрации.                                                                     |
| **interaction_logs**         | Может использоваться для обучения, feedback.                                            |
| **feedback.db** (SQLite)     | Обратная связь пользователей.                                                           |
| **Redis rag*ctx:*, plan:\_** | TTL + maxmemory-policy уже управляют. Ручная очистка может ухудшить производительность. |

## ✅ Данные, безопасные для очистки (консервативно)

| Таблица                  | Условие                                               | Рекомендация                                                                                                   |
| ------------------------ | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **real_time_metrics**    | Временные метрики (cpu_temp, tokens/s и т.д.)         | Удалять записи старше 90 дней. По умолчанию не очищать автоматически.                                          |
| **semantic_ai_cache**    | Кэш ответов (query→response). Колонка `last_used_at`. | Очищать записи, не использовавшиеся > 90 дней. Таблица может быть пустой.                                      |
| **embedding_cache** (БД) | Кэш эмбеддингов в knowledge_os. `last_used_at`.       | Не используется atra-web-ide backend (там in-memory). При необходимости — очистка по `last_used_at` > 90 дней. |

## knowledge_cleaner (архивация узлов)

`knowledge_os/app/knowledge_cleaner.py` переносит в `knowledge_nodes_archive` узлы с `usage_count=0`, `created_at` > 30 дней, `confidence_score` < 0.9. **Восстановление:** `psql -f scripts/restore_knowledge_from_archive.sql`

## ⚠️ Уже есть

- **CacheCleanupTask** (knowledge_os) — очищает `semantic_ai_cache` по `expires_at`, но колонки `expires_at` нет в схеме → фактически ничего не удаляет.
- **RAG Context Cache** — Redis с TTL, истекает сам.
- **Plan cache** — Redis с TTL.
- **EmbeddingBatchProcessor** — in-memory, очищается через `POST /api/rag-optimization/cache/clear`.

## Рекомендации по внедрению

1. **Не внедрять** массовую очистку `knowledge_nodes`, архивацию, VACUUM/REINDEX по умолчанию.
2. **Реализовано** — `DataRetentionManager` очищает только `real_time_metrics` и `semantic_ai_cache`:
   - DRY-RUN по умолчанию: `POST /api/data-retention/cleanup?dry_run=true`
   - Реальная очистка: `POST /api/data-retention/cleanup?dry_run=false`
   - `DATA_RETENTION_DAYS=90` (по умолчанию)
3. **Redis** — не трогать; полагаться на TTL и `maxmemory-policy allkeys-lru`.
4. **VACUUM** — только ручной, по решению админа, вне автоматики.
