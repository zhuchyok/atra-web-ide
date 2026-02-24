-- Миграция для создания таблицы явного feedback от пользователей
-- Singularity 8.0: Intelligent Improvements

CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT NOT NULL,
    expert_name TEXT NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN ('positive', 'negative')),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),  -- Опциональная оценка 1-5
    comment TEXT,  -- Опциональный комментарий
    metadata JSONB,  -- Дополнительные данные (routing_source, performance_score, etc.)
    processed BOOLEAN DEFAULT FALSE,  -- Обработан ли feedback для оптимизации промптов
    processed_at TIMESTAMP WITH TIME ZONE
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_user_feedback_user_id ON user_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_expert_name ON user_feedback(expert_name);
CREATE INDEX IF NOT EXISTS idx_user_feedback_type ON user_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_user_feedback_created_at ON user_feedback(created_at);

-- Дозаполнить колонки, если таблица уже существовала без них
ALTER TABLE user_feedback ADD COLUMN IF NOT EXISTS processed BOOLEAN DEFAULT FALSE;
ALTER TABLE user_feedback ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;
CREATE INDEX IF NOT EXISTS idx_user_feedback_processed ON user_feedback(processed);

-- Комментарии
COMMENT ON TABLE user_feedback IS 'Явный feedback от пользователей (👍/👎) для улучшения промптов';
COMMENT ON COLUMN user_feedback.feedback_type IS 'Тип feedback: positive (👍) или negative (👎)';
COMMENT ON COLUMN user_feedback.processed IS 'Обработан ли feedback для оптимизации промптов';
