-- Проверка индексов pgvector на knowledge_nodes
-- Запуск: psql $DATABASE_URL -f scripts/check_pgvector_index.sql

SELECT
    indexname,
    indexdef,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS size
FROM pg_indexes
WHERE tablename = 'knowledge_nodes'
  AND indexdef LIKE '%embedding%'
ORDER BY indexname;
