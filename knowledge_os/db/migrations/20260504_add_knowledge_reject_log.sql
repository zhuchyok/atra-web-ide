CREATE TABLE IF NOT EXISTS knowledge_reject_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_hash TEXT NOT NULL,
    source_type TEXT NOT NULL,
    reject_reason TEXT NOT NULL,
    gate_stage TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_reject_log_reason_created
    ON knowledge_reject_log (reject_reason, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_reject_log_source_created
    ON knowledge_reject_log (source_type, created_at DESC);
