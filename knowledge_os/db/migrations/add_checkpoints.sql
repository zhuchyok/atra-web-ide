-- Checkpoints table for long-term planning
-- Created: 2026-04-18

CREATE TABLE IF NOT EXISTS checkpoints (
    checkpoint_id VARCHAR(255) PRIMARY KEY,
    task_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL,
    state JSONB NOT NULL DEFAULT '{}',
    step INTEGER NOT NULL DEFAULT 0,
    progress DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    parent_checkpoint_id VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_task_id ON checkpoints(task_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_agent ON checkpoints(agent_name);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created ON checkpoints(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_checkpoints_parent ON checkpoints(parent_checkpoint_id);

COMMENT ON TABLE checkpoints IS 'Checkpoints for long-term task execution and recovery';
COMMENT ON COLUMN checkpoints.progress IS 'Progress 0.0-1.0';
COMMENT ON COLUMN checkpoints.expires_at IS 'Auto-delete after this time';
COMMENT ON COLUMN checkpoints.parent_checkpoint_id IS 'For hierarchical checkpoint chains';
