-- Fix embedding dimensions: ensure 768 (nomic-embed-text) everywhere.
-- Run once. Alters only when column dimension is not 768 (atttypmod != 768); existing 768-dim rows preserved.
-- Ref: CHECK_TASKS_IN_PROGRESS_20260203, MASTER_REFERENCE § embedding dimension.

-- semantic_ai_cache: used by semantic_cache.save_to_cache (Ollama nomic-embed-text → 768)
DO $$
DECLARE
    dims int;
BEGIN
    SELECT a.atttypmod INTO dims
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    WHERE c.relname = 'semantic_ai_cache' AND a.attname = 'embedding' AND NOT a.attisdropped AND a.attnum > 0;
    IF dims IS NOT NULL AND dims != 768 THEN
        ALTER TABLE semantic_ai_cache
        ALTER COLUMN embedding TYPE vector(768) USING NULL;
        RAISE NOTICE 'semantic_ai_cache.embedding % → vector(768)', dims;
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'semantic_ai_cache.embedding skip: %', SQLERRM;
END $$;

-- embedding_cache: used by embedding_optimizer
DO $$
DECLARE
    dims int;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'embedding_cache') THEN
        RETURN;
    END IF;
    SELECT a.atttypmod INTO dims
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    WHERE c.relname = 'embedding_cache' AND a.attname = 'embedding' AND NOT a.attisdropped AND a.attnum > 0;
    IF dims IS NOT NULL AND dims != 768 THEN
        ALTER TABLE embedding_cache
        ALTER COLUMN embedding TYPE vector(768) USING NULL;
        RAISE NOTICE 'embedding_cache.embedding % → vector(768)', dims;
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'embedding_cache.embedding skip: %', SQLERRM;
END $$;
