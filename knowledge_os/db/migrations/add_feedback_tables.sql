-- Миграция для таблиц Feedback и Adaptive Learning
-- Создает таблицы для сбора feedback и адаптивного обучения

-- Таблица для хранения feedback
CREATE TABLE IF NOT EXISTS feedback_data (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    response TEXT,
    routing_source VARCHAR(50),
    rerouted_to_cloud BOOLEAN DEFAULT FALSE,
    reroute_reason VARCHAR(100),
    quality_score FLOAT,
    feedback_type VARCHAR(50) DEFAULT 'implicit',
    is_positive BOOLEAN,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для feedback
CREATE INDEX IF NOT EXISTS idx_feedback_routing_source ON feedback_data(routing_source);
CREATE INDEX IF NOT EXISTS idx_feedback_rerouted ON feedback_data(rerouted_to_cloud);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback_data(created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback_data(feedback_type);

-- Таблица для логов адаптивного обучения
CREATE TABLE IF NOT EXISTS adaptive_learning_logs (
    id SERIAL PRIMARY KEY,
    cycle_type VARCHAR(50) NOT NULL,  -- 'feedback_analysis', 'example_update', 'prioritization'
    examples_updated INTEGER DEFAULT 0,
    examples_deleted INTEGER DEFAULT 0,
    examples_added INTEGER DEFAULT 0,
    feedback_analyzed INTEGER DEFAULT 0,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индекс для логов
CREATE INDEX IF NOT EXISTS idx_adaptive_logs_created_at ON adaptive_learning_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_adaptive_logs_cycle_type ON adaptive_learning_logs(cycle_type);

-- Комментарии
COMMENT ON TABLE feedback_data IS 'Feedback от пользователей и системы для адаптивного обучения';
COMMENT ON TABLE adaptive_learning_logs IS 'Логи циклов адаптивного обучения';

