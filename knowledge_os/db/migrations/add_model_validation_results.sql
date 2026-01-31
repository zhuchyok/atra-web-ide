-- Миграция для добавления таблицы результатов валидации моделей
-- Singularity 7.5: Observability and Autonomous Operations

CREATE TABLE IF NOT EXISTS model_validation_results (
    id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    ollama_url TEXT NOT NULL,
    accuracy NUMERIC NOT NULL, -- 0.0 - 1.0
    latency_ms NUMERIC NOT NULL,
    quality_score NUMERIC NOT NULL, -- 0.0 - 1.0
    tokens_used INTEGER DEFAULT 0,
    errors JSONB, -- Список ошибок при валидации
    passed BOOLEAN NOT NULL, -- Прошла ли модель валидацию
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_model_val_name ON model_validation_results(model_name);
CREATE INDEX IF NOT EXISTS idx_model_val_created_at ON model_validation_results(created_at);
CREATE INDEX IF NOT EXISTS idx_model_val_passed ON model_validation_results(passed);
CREATE INDEX IF NOT EXISTS idx_model_val_quality ON model_validation_results(quality_score DESC);

-- Индекс для быстрого поиска моделей с низким качеством
CREATE INDEX IF NOT EXISTS idx_model_val_low_quality ON model_validation_results(quality_score) WHERE quality_score < 0.8;

COMMENT ON TABLE model_validation_results IS 'Результаты кросс-валидации моделей для сравнения качества';
COMMENT ON COLUMN model_validation_results.model_name IS 'Имя модели';
COMMENT ON COLUMN model_validation_results.ollama_url IS 'URL Ollama инстанса';
COMMENT ON COLUMN model_validation_results.accuracy IS 'Точность модели (0.0 - 1.0)';
COMMENT ON COLUMN model_validation_results.latency_ms IS 'Задержка ответа в миллисекундах';
COMMENT ON COLUMN model_validation_results.quality_score IS 'Общий показатель качества (комбинация accuracy и latency)';
COMMENT ON COLUMN model_validation_results.tokens_used IS 'Количество использованных токенов';
COMMENT ON COLUMN model_validation_results.errors IS 'Список ошибок при валидации в формате JSON';
COMMENT ON COLUMN model_validation_results.passed IS 'Прошла ли модель валидацию (accuracy >= 0.8)';

