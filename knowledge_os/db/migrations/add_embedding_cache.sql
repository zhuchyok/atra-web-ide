-- Миграция для создания таблицы кэша эмбеддингов
-- Singularity 8.0: Performance Optimization

CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash TEXT PRIMARY KEY,
    normalized_text TEXT NOT NULL,
    embedding vector(768),  -- Размер зависит от модели (nomic-embed-text использует 768)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_embedding_cache_created_at ON embedding_cache(created_at);

-- Комментарии
COMMENT ON TABLE embedding_cache IS 'Кэш эмбеддингов для ускорения поиска в semantic_ai_cache';
COMMENT ON COLUMN embedding_cache.text_hash IS 'MD5 хэш нормализованного текста';
COMMENT ON COLUMN embedding_cache.normalized_text IS 'Нормализованный текст (для отладки)';
COMMENT ON COLUMN embedding_cache.embedding IS 'Векторное представление текста';

