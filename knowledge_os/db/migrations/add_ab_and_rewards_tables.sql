-- [SINGULARITY 28.0] A/B Testing and Rewards tables
-- Created: 2026-04-20

-- Agent A/B Results
CREATE TABLE IF NOT EXISTS agent_ab_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_name TEXT NOT NULL,
    strategy TEXT NOT NULL,
    task_id TEXT,
    score FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ab_expert_name ON agent_ab_results(expert_name);
CREATE INDEX IF NOT EXISTS idx_ab_strategy ON agent_ab_results(strategy);
CREATE INDEX IF NOT EXISTS idx_ab_created_at ON agent_ab_results(created_at);

-- Interaction Rewards (Constitutional)
CREATE TABLE IF NOT EXISTS interaction_rewards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_log_id UUID REFERENCES interaction_logs(id),
    expert_name TEXT NOT NULL,
    reward_type TEXT NOT NULL,
    reward_value FLOAT DEFAULT 0.0,
    reason TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Backward-compatibility for partially created historical schemas.
ALTER TABLE interaction_rewards ADD COLUMN IF NOT EXISTS interaction_log_id UUID;
ALTER TABLE interaction_rewards ADD COLUMN IF NOT EXISTS reward_type TEXT;
ALTER TABLE interaction_rewards ADD COLUMN IF NOT EXISTS reward_value FLOAT DEFAULT 0.0;
ALTER TABLE interaction_rewards ADD COLUMN IF NOT EXISTS reason TEXT;
ALTER TABLE interaction_rewards ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
ALTER TABLE interaction_rewards ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_rewards_expert ON interaction_rewards(expert_name);
CREATE INDEX IF NOT EXISTS idx_rewards_type ON interaction_rewards(reward_type);
CREATE INDEX IF NOT EXISTS idx_rewards_interaction_log_id ON interaction_rewards(interaction_log_id);

-- Knowledge Edges (Graph connections)
CREATE TABLE IF NOT EXISTS knowledge_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES knowledge_nodes(id),
    target_id UUID NOT NULL REFERENCES knowledge_nodes(id),
    relationship_type TEXT DEFAULT 'related',
    weight FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Backward-compatibility for historical partial schemas.
ALTER TABLE knowledge_edges ADD COLUMN IF NOT EXISTS source_id UUID;
ALTER TABLE knowledge_edges ADD COLUMN IF NOT EXISTS target_id UUID;
ALTER TABLE knowledge_edges ADD COLUMN IF NOT EXISTS relationship_type TEXT DEFAULT 'related';
ALTER TABLE knowledge_edges ADD COLUMN IF NOT EXISTS weight FLOAT DEFAULT 1.0;
ALTER TABLE knowledge_edges ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
ALTER TABLE knowledge_edges ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_edges_source ON knowledge_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON knowledge_edges(target_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique ON knowledge_edges(source_id, target_id, relationship_type);

-- Add columns to existing tables if not exist
ALTER TABLE interaction_logs ADD COLUMN IF NOT EXISTS quality_score FLOAT;
ALTER TABLE interaction_logs ADD COLUMN IF NOT EXISTS strategy_used TEXT;
ALTER TABLE interaction_logs ADD COLUMN IF NOT EXISTS symbols_used JSONB DEFAULT '[]';
