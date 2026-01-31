-- Миграция для создания таблиц аналитики использования
-- Singularity 8.0: Monitoring and Analytics

-- Аналитика по пользователям
CREATE TABLE IF NOT EXISTS user_analytics (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_length INTEGER,
    response_length INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Аналитика по экспертам
CREATE TABLE IF NOT EXISTS expert_analytics (
    id SERIAL PRIMARY KEY,
    expert_name TEXT NOT NULL,
    request_count INTEGER DEFAULT 1,
    created_at DATE DEFAULT CURRENT_DATE,
    UNIQUE(expert_name, created_at)
);

-- Аналитика по моделям
CREATE TABLE IF NOT EXISTS model_analytics (
    id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    request_count INTEGER DEFAULT 1,
    avg_latency_ms FLOAT,
    total_tokens INTEGER DEFAULT 0,
    created_at DATE DEFAULT CURRENT_DATE,
    UNIQUE(model_name, created_at)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_user_analytics_user_id ON user_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_user_analytics_created_at ON user_analytics(created_at);
CREATE INDEX IF NOT EXISTS idx_expert_analytics_expert_name ON expert_analytics(expert_name);
CREATE INDEX IF NOT EXISTS idx_expert_analytics_created_at ON expert_analytics(created_at);
CREATE INDEX IF NOT EXISTS idx_model_analytics_model_name ON model_analytics(model_name);
CREATE INDEX IF NOT EXISTS idx_model_analytics_created_at ON model_analytics(created_at);

-- Комментарии
COMMENT ON TABLE user_analytics IS 'Аналитика использования по пользователям';
COMMENT ON TABLE expert_analytics IS 'Аналитика использования по экспертам';
COMMENT ON TABLE model_analytics IS 'Аналитика использования по моделям';

