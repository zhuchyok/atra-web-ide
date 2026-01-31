-- Migration: Add Code Smell tables (Singularity 9.0)
-- Purpose: Store code smell predictions and training data for bug prediction
-- Date: 2026-01-16

CREATE TABLE IF NOT EXISTS code_smell_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path VARCHAR(500),
    code_snippet TEXT,
    predicted_issues JSONB,  -- {bug_probability, likely_issues, risk_files}
    actual_bugs INTEGER DEFAULT 0,  -- Подтвержденные баги (через 30 дней)
    precision_score FLOAT,   -- Точность предсказания
    recall_score FLOAT,      -- Полнота предсказания
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS code_smell_training_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path VARCHAR(500),
    code_features JSONB,  -- {complexity, patterns, coverage, ...}
    actual_bug BOOLEAN,   -- Был ли баг в следующие 30 дней
    bug_type VARCHAR(100), -- null_pointer, race_condition, etc.
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_code_smell_predictions_file ON code_smell_predictions(file_path);
CREATE INDEX IF NOT EXISTS idx_code_smell_training_bug ON code_smell_training_data(actual_bug);
CREATE INDEX IF NOT EXISTS idx_code_smell_training_type ON code_smell_training_data(bug_type);

COMMENT ON TABLE code_smell_predictions IS 'Предсказания багов в коде для Code-Smell Predictor (Singularity 9.0)';
COMMENT ON TABLE code_smell_training_data IS 'Данные для обучения ML модели предсказания багов (Singularity 9.0)';
COMMENT ON COLUMN code_smell_predictions.predicted_issues IS 'JSON с предсказанием: {bug_probability, likely_issues, risk_files}';
COMMENT ON COLUMN code_smell_predictions.actual_bugs IS 'Количество подтвержденных багов через 30 дней (для валидации)';
COMMENT ON COLUMN code_smell_training_data.code_features IS 'JSON с features кода: {cyclomatic_complexity, function_count, class_count, anti_patterns, ...}';

