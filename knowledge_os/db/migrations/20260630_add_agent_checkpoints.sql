-- Agent State Checkpoints for save/restore/rollback
-- Created: 2026-06-30
-- Depends on: PostgreSQL 14+ (JSONB, TIMESTAMPTZ)

CREATE TABLE IF NOT EXISTS agent_checkpoints (
    id VARCHAR(64) PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    state_type VARCHAR(50) NOT NULL,
    state_data JSONB NOT NULL,
    parent_id VARCHAR(64),
    tags JSONB DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_ac_agent ON agent_checkpoints(agent_name);
CREATE INDEX IF NOT EXISTS idx_ac_created ON agent_checkpoints(created_at);
CREATE INDEX IF NOT EXISTS idx_ac_type ON agent_checkpoints(state_type);
CREATE INDEX IF NOT EXISTS idx_ac_agent_type ON agent_checkpoints(agent_name, state_type);

COMMENT ON TABLE agent_checkpoints IS 'Agent state checkpoints for save/restore/rollback across the multi-agent system';
COMMENT ON COLUMN agent_checkpoints.id IS 'Short UUID (8 chars) — checkpoint identifier';
COMMENT ON COLUMN agent_checkpoints.agent_name IS 'Agent name (e.g. Victoria, Veronica, Анна)';
COMMENT ON COLUMN agent_checkpoints.state_type IS 'Checkpoint type: task, memory, session, full, rollback_safety';
COMMENT ON COLUMN agent_checkpoints.state_data IS 'Full serialized agent state as JSONB';
COMMENT ON COLUMN agent_checkpoints.parent_id IS 'Previous checkpoint ID for rollback chain traversal';
COMMENT ON COLUMN agent_checkpoints.tags IS 'Arbitrary tags for filtering (e.g. ["task", "victoria"])';
