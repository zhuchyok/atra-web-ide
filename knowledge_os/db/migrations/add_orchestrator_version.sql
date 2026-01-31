-- Migration: Add orchestrator_version to tasks for A/B metrics (V2 vs existing)
-- Date: 2026-01-27
-- Idempotent: safe to run multiple times.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tasks' AND column_name = 'orchestrator_version'
    ) THEN
        ALTER TABLE tasks ADD COLUMN orchestrator_version VARCHAR(20) DEFAULT NULL;
    END IF;
END $$;

COMMENT ON COLUMN tasks.orchestrator_version IS 'A/B: v2 = EnhancedOrchestratorV2, existing = legacy/oracle';

CREATE INDEX IF NOT EXISTS idx_tasks_orchestrator_version ON tasks (orchestrator_version) WHERE orchestrator_version IS NOT NULL;
