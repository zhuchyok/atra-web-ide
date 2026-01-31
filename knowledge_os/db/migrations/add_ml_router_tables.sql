-- Миграция для таблиц ML Router
-- Создает таблицы для сбора данных о решениях роутера и обучения ML-модели

-- Таблица для хранения данных о решениях роутера (training data)
CREATE TABLE IF NOT EXISTS ml_router_training_data (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,  -- coding, reasoning, general
    prompt_length INTEGER NOT NULL,
    category VARCHAR(100),
    selected_route VARCHAR(50) NOT NULL,  -- local_mac, local_server, cloud
    performance_score FLOAT,
    tokens_saved INTEGER DEFAULT 0,
    latency_ms FLOAT,
    quality_score FLOAT,  -- из Quality Assurance
    success BOOLEAN DEFAULT TRUE,
    features JSONB,  -- дополнительные features для ML
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_ml_router_task_type ON ml_router_training_data(task_type);
CREATE INDEX IF NOT EXISTS idx_ml_router_route ON ml_router_training_data(selected_route);
CREATE INDEX IF NOT EXISTS idx_ml_router_created_at ON ml_router_training_data(created_at);
CREATE INDEX IF NOT EXISTS idx_ml_router_success ON ml_router_training_data(success);

-- Таблица для хранения предсказаний ML-модели
CREATE TABLE IF NOT EXISTS ml_router_predictions (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    prompt_length INTEGER NOT NULL,
    category VARCHAR(100),
    predicted_route VARCHAR(50) NOT NULL,
    confidence FLOAT,
    actual_route VARCHAR(50),  -- фактический выбранный маршрут
    was_correct BOOLEAN,  -- было ли предсказание правильным
    features JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы для анализа предсказаний
CREATE INDEX IF NOT EXISTS idx_ml_router_pred_task_type ON ml_router_predictions(task_type);
CREATE INDEX IF NOT EXISTS idx_ml_router_pred_created_at ON ml_router_predictions(created_at);
CREATE INDEX IF NOT EXISTS idx_ml_router_pred_correct ON ml_router_predictions(was_correct);

-- Комментарии
COMMENT ON TABLE ml_router_training_data IS 'Данные для обучения ML-модели роутинга';
COMMENT ON TABLE ml_router_predictions IS 'Предсказания ML-модели роутинга для анализа';

