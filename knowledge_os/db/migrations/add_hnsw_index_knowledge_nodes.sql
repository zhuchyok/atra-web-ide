-- HNSW индекс для knowledge_nodes.embedding (быстрее IVFFlat для поиска)
-- Выполнить: psql $DATABASE_URL -f add_hnsw_index_knowledge_nodes.sql
-- Ollama + MLX: эмбеддинги через Ollama (nomic-embed-text), векторный поиск ускоряется

-- Проверка: SELECT indexname FROM pg_indexes WHERE tablename = 'knowledge_nodes' AND indexdef LIKE '%embedding%';

-- Создаём HNSW (ivfflat остаётся как fallback)
DROP INDEX IF EXISTS knowledge_nodes_embedding_hnsw_idx;
CREATE INDEX knowledge_nodes_embedding_hnsw_idx
ON knowledge_nodes
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Для поиска с ограничением ef_search (по умолчанию 40):
-- SET hnsw.ef_search = 64;  -- в сессии при необходимости
