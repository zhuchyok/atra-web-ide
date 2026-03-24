-- Миграция: добавить metadata JSONB в semantic_ai_cache
-- Нужна для хранения флагов сжатия и других метаданных кэша
-- Применена: 2026-03-22 (column "metadata" does not exist)

ALTER TABLE semantic_ai_cache
    ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_semantic_ai_cache_metadata
    ON semantic_ai_cache USING GIN (metadata);

COMMENT ON COLUMN semantic_ai_cache.metadata IS 'JSON-метаданные кэша: precompressed, compression_ratio и др.';
