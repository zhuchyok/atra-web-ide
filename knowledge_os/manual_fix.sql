-- [SINGULARITY 31.2] Manual Schema Fix
-- Добавляем недостающие колонки и таблицы для корректной работы воркеров и системы обучения

-- 1. Добавляем колонку last_llm_call_at и retry_after в таблицу tasks
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS last_llm_call_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS retry_after TIMESTAMP WITH TIME ZONE;

-- 2. Обновляем таблицу experts
ALTER TABLE experts ADD COLUMN IF NOT EXISTS auto_dna_sync BOOLEAN DEFAULT TRUE;
ALTER TABLE experts ADD COLUMN IF NOT EXISTS last_dna_sync TIMESTAMP WITH TIME ZONE;
ALTER TABLE experts ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 3. Создаем таблицу expert_dna_overrides
CREATE TABLE IF NOT EXISTS expert_dna_overrides (
    id SERIAL PRIMARY KEY,
    expert_id UUID REFERENCES experts(id) ON DELETE CASCADE,
    custom_instructions TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255) DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_expert_dna_overrides_expert_id ON expert_dna_overrides(expert_id) WHERE is_active = TRUE;

-- 4. Создаем таблицу model_performance_log
CREATE TABLE IF NOT EXISTS model_performance_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(255) NOT NULL,
    success BOOLEAN DEFAULT TRUE,
    quality_score FLOAT DEFAULT 1.0,
    latency_ms FLOAT,
    response_length INTEGER,
    task_id UUID,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для model_performance_log
CREATE INDEX IF NOT EXISTS idx_model_perf_name ON model_performance_log (model_name);
CREATE INDEX IF NOT EXISTS idx_model_perf_success ON model_performance_log (success);
CREATE INDEX IF NOT EXISTS idx_model_perf_created ON model_performance_log (created_at DESC);

-- 3. Создаем таблицу corporation_learning_log
CREATE TABLE IF NOT EXISTS corporation_learning_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_number INTEGER,
    error_analysis JSONB DEFAULT '{}',
    performance_analysis JSONB DEFAULT '{}',
    improvements JSONB DEFAULT '{}',
    applied_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для corporation_learning_log
CREATE INDEX IF NOT EXISTS idx_corp_learning_created ON corporation_learning_log (created_at DESC);
