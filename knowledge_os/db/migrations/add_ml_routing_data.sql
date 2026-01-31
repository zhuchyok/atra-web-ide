-- Миграция для создания таблицы данных обучения ML роутера
-- Singularity 8.0: Intelligent Improvements

CREATE TABLE IF NOT EXISTS ml_routing_training_data (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    task_type TEXT NOT NULL,
    prompt_length INTEGER NOT NULL,
    category TEXT,
    selected_route TEXT NOT NULL,
    performance_score FLOAT,
    tokens_saved INTEGER DEFAULT 0,
    latency_ms FLOAT,
    quality_score FLOAT,
    success BOOLEAN DEFAULT TRUE,
    features JSONB,
    actual_route_used TEXT,  -- Фактически использованный роут (для обучения)
    user_satisfaction FLOAT,  -- Оценка пользователя (если есть feedback)
    CONSTRAINT valid_performance_score CHECK (performance_score IS NULL OR (performance_score >= 0 AND performance_score <= 1)),
    CONSTRAINT valid_quality_score CHECK (quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1))
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_ml_routing_created_at ON ml_routing_training_data(created_at);
CREATE INDEX IF NOT EXISTS idx_ml_routing_task_type ON ml_routing_training_data(task_type);
CREATE INDEX IF NOT EXISTS idx_ml_routing_category ON ml_routing_training_data(category);
CREATE INDEX IF NOT EXISTS idx_ml_routing_success ON ml_routing_training_data(success);
CREATE INDEX IF NOT EXISTS idx_ml_routing_performance ON ml_routing_training_data(performance_score) WHERE performance_score IS NOT NULL;

-- Комментарии
COMMENT ON TABLE ml_routing_training_data IS 'Данные для обучения ML модели роутинга';
COMMENT ON COLUMN ml_routing_training_data.task_type IS 'Тип задачи (coding, general, research, etc.)';
COMMENT ON COLUMN ml_routing_training_data.selected_route IS 'Выбранный роут (local, cloud, veronica_web, etc.)';
COMMENT ON COLUMN ml_routing_training_data.actual_route_used IS 'Фактически использованный роут (может отличаться от selected_route)';
COMMENT ON COLUMN ml_routing_training_data.user_satisfaction IS 'Оценка пользователя (0-1) на основе feedback';

