-- Миграция: исправить размерность vector в embedding_cache 384 → 768
-- Причина: nomic-embed-text возвращает 768 измерений, таблица была создана с 384
-- Применена: 2026-03-22 (ERROR: expected 384 dimensions, not 768)
-- Внимание: TRUNCATE — старые эмбеддинги другой размерности несовместимы, кэш перестроится сам

DROP INDEX IF EXISTS idx_embedding_cache_embedding;
TRUNCATE TABLE embedding_cache;
ALTER TABLE embedding_cache ALTER COLUMN embedding TYPE vector(768) USING NULL;
CREATE INDEX IF NOT EXISTS idx_embedding_cache_embedding
    ON embedding_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

COMMENT ON COLUMN embedding_cache.embedding IS 'Вектор 768 измерений (nomic-embed-text)';
