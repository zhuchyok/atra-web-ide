CREATE TABLE IF NOT EXISTS expert_mutations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id UUID REFERENCES experts(id) ON DELETE CASCADE,
    mutated_prompt TEXT NOT NULL,
    base_version INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'shadow',
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    draw_count INTEGER DEFAULT 0,
    total_tests INTEGER DEFAULT 0,
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_expert_mutations_expert_status ON expert_mutations (expert_id, status);
