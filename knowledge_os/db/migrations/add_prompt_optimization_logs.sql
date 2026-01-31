-- Миграция для добавления таблицы логирования оптимизации промптов
-- Singularity 7.5: Observability and Autonomous Operations

CREATE TABLE IF NOT EXISTS prompt_optimization_logs (
    id SERIAL PRIMARY KEY,
    expert_name TEXT NOT NULL,
    original_prompt TEXT NOT NULL,
    improved_prompt TEXT NOT NULL,
    improvement_reason TEXT,
    expected_impact TEXT, -- 'high', 'medium', 'low'
    confidence NUMERIC, -- 0.0 - 1.0
    applied BOOLEAN DEFAULT FALSE,
    performance_before NUMERIC, -- Performance score до применения
    performance_after NUMERIC, -- Performance score после применения
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prompt_opt_expert ON prompt_optimization_logs(expert_name);
CREATE INDEX IF NOT EXISTS idx_prompt_opt_created_at ON prompt_optimization_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_prompt_opt_applied ON prompt_optimization_logs(applied);
CREATE INDEX IF NOT EXISTS idx_prompt_opt_impact ON prompt_optimization_logs(expected_impact);

COMMENT ON TABLE prompt_optimization_logs IS 'Логи предложений по оптимизации системных промптов на основе анализа успешных диалогов';
COMMENT ON COLUMN prompt_optimization_logs.expert_name IS 'Имя эксперта, для которого предложено улучшение';
COMMENT ON COLUMN prompt_optimization_logs.original_prompt IS 'Оригинальный системный промпт';
COMMENT ON COLUMN prompt_optimization_logs.improved_prompt IS 'Улучшенный системный промпт';
COMMENT ON COLUMN prompt_optimization_logs.improvement_reason IS 'Причина предложения улучшения';
COMMENT ON COLUMN prompt_optimization_logs.expected_impact IS 'Ожидаемое влияние улучшения (high, medium, low)';
COMMENT ON COLUMN prompt_optimization_logs.confidence IS 'Уверенность в улучшении (0.0 - 1.0)';
COMMENT ON COLUMN prompt_optimization_logs.applied IS 'Было ли улучшение применено';
COMMENT ON COLUMN prompt_optimization_logs.performance_before IS 'Performance score до применения улучшения';
COMMENT ON COLUMN prompt_optimization_logs.performance_after IS 'Performance score после применения улучшения';

