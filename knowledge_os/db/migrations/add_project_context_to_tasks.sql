-- Migration: Add project_context to tasks for multi-tenant isolation
-- Date: 2026-02-03
-- Purpose: Filter and scope tasks by project; dashboard/reports can filter by project_context.

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS project_context VARCHAR(255) DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_tasks_project_context ON tasks (project_context) WHERE project_context IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_status_project_context ON tasks (status, project_context);

COMMENT ON COLUMN tasks.project_context IS 'Slug from projects table; NULL = legacy or internal task';
