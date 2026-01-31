-- Migration to add semantic AI cache
CREATE TABLE IF NOT EXISTS semantic_ai_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    embedding vector(768),
    expert_name VARCHAR(255),
    usage_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(query_text, expert_name)
);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_embedding ON semantic_ai_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_semantic_cache_expert ON semantic_ai_cache (expert_name);

