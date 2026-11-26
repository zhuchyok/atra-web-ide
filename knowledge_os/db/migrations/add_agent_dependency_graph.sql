-- Migration: Add agent dependency graph table
-- Date: 2026-06-30
-- Version: Singularity 31.4

-- Agent dependency edges: tracks every agent→agent interaction
CREATE TABLE IF NOT EXISTS agent_dependency_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_agent VARCHAR(255) NOT NULL,
    target_agent VARCHAR(255) NOT NULL,
    edge_type VARCHAR(50) NOT NULL,
    task_id VARCHAR(255),
    latency_ms DOUBLE PRECISION DEFAULT 0,
    success BOOLEAN DEFAULT TRUE,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ade_source ON agent_dependency_edges(source_agent);
CREATE INDEX IF NOT EXISTS idx_ade_target ON agent_dependency_edges(target_agent);
CREATE INDEX IF NOT EXISTS idx_ade_recorded_at ON agent_dependency_edges(recorded_at);

-- Composite index for common query patterns: who called whom
CREATE INDEX IF NOT EXISTS idx_ade_source_target ON agent_dependency_edges(source_agent, target_agent);

-- Index for edge type filtering
CREATE INDEX IF NOT EXISTS idx_ade_edge_type ON agent_dependency_edges(edge_type);

-- Index for task_id lookups
CREATE INDEX IF NOT EXISTS idx_ade_task_id ON agent_dependency_edges(task_id);
