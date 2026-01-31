-- Migration: Add Tacit Knowledge tables (Singularity 9.0)
-- Purpose: Store user style profiles for tacit knowledge extraction
-- Date: 2026-01-16

CREATE TABLE IF NOT EXISTS user_style_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_identifier VARCHAR(255) NOT NULL,
    style_vector FLOAT[],  -- Embedding вектор стиля
    preferences JSONB,     -- {naming_convention, error_handling, testing_style, ...}
    similarity_score FLOAT DEFAULT 0.0,  -- Cosine similarity с эталонным стилем
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_style_profiles_user ON user_style_profiles(user_identifier);
CREATE INDEX IF NOT EXISTS idx_user_style_profiles_similarity ON user_style_profiles(similarity_score DESC);

COMMENT ON TABLE user_style_profiles IS 'Стилевые профили пользователей для Tacit Knowledge Extractor (Singularity 9.0)';
COMMENT ON COLUMN user_style_profiles.style_vector IS 'Embedding вектор стиля пользователя (для cosine similarity)';
COMMENT ON COLUMN user_style_profiles.preferences IS 'JSON с предпочтениями стиля: naming_convention, error_handling, testing_style, documentation_style, code_structure, variable_naming, function_style';
COMMENT ON COLUMN user_style_profiles.similarity_score IS 'Cosine similarity между стилем пользователя и эталонным стилем (для метрик)';

