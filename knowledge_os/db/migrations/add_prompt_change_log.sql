-- Singularity 10.0: Версионирование и откат изменений промптов
-- Таблица prompt_change_log для Safe Feedback Loops (ExpeL/Microsoft практики)

CREATE TABLE IF NOT EXISTS prompt_change_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id UUID REFERENCES experts(id) ON DELETE CASCADE,
    old_prompt_hash VARCHAR(64) NOT NULL,  -- SHA256 хеш предыдущего промпта
    new_prompt_hash VARCHAR(64) NOT NULL,  -- SHA256 хеш нового промпта
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reverted_at TIMESTAMP WITH TIME ZONE,
    reverted_reason TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_prompt_change_log_expert ON prompt_change_log (expert_id);
CREATE INDEX IF NOT EXISTS idx_prompt_change_log_applied ON prompt_change_log (applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_prompt_change_log_reverted ON prompt_change_log (reverted_at) WHERE reverted_at IS NULL;

COMMENT ON TABLE prompt_change_log IS 'Singularity 10.0: лог изменений промптов для версионирования и отката';
