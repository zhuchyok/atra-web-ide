-- Canonical mapping between Redis/Blackboard external task IDs and Postgres UUID task IDs.
-- This allows workers to resolve non-UUID task identifiers before SQL status updates.
CREATE TABLE IF NOT EXISTS task_identity_map (
    external_task_id TEXT PRIMARY KEY,
    canonical_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_identity_map_canonical_task_id
    ON task_identity_map (canonical_task_id);
