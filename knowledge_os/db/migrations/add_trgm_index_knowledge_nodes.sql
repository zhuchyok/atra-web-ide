-- Миграция: добавить pg_trgm индекс на knowledge_nodes.content для ILIKE запросов
-- Причина: content ILIKE $1 делал seq scan на 94K строк (580 MB) → 513% CPU на postgres
-- Применена: 2026-03-08 (высокий CPU knowledge_postgres из-за неиндексированных ILIKE)
-- Эффект: CPU знизился с 513% → ~90-126% (только HNSW vector search)

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_nodes_content_trgm
    ON knowledge_nodes USING GIN (content gin_trgm_ops);

COMMENT ON INDEX idx_knowledge_nodes_content_trgm IS 
    'Trigram индекс для быстрых ILIKE запросов по content. Поддерживает content ILIKE %pattern%.';
