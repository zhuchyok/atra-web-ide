-- Migration: Task orchestration world-class schema (parent/child tasks, expert specializations)
-- Date: 2026-01-30
-- Version: Singularity 9.0 / Orchestration Plan Audit
-- Idempotent: safe to run multiple times.

-- ============================================
-- 1. experts.is_active (required by enhanced_orchestrator WHERE is_active = true)
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'experts' AND column_name = 'is_active'
    ) THEN
        ALTER TABLE experts ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
    END IF;
END $$;

-- ============================================
-- 2. tasks: result column (init.sql has it; add_tasks_table does not)
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tasks' AND column_name = 'result'
    ) THEN
        ALTER TABLE tasks ADD COLUMN result TEXT;
    END IF;
END $$;

-- ============================================
-- 3. tasks: parent/child and orchestration columns
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tasks' AND column_name = 'parent_task_id'
    ) THEN
        ALTER TABLE tasks ADD COLUMN parent_task_id UUID REFERENCES tasks(id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tasks' AND column_name = 'task_type'
    ) THEN
        ALTER TABLE tasks ADD COLUMN task_type VARCHAR(50) DEFAULT 'simple';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tasks' AND column_name = 'complexity_score'
    ) THEN
        ALTER TABLE tasks ADD COLUMN complexity_score FLOAT DEFAULT 1.0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tasks' AND column_name = 'required_models'
    ) THEN
        ALTER TABLE tasks ADD COLUMN required_models JSONB;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'tasks' AND column_name = 'estimated_duration_min'
    ) THEN
        ALTER TABLE tasks ADD COLUMN estimated_duration_min INTEGER;
    END IF;
END $$;

COMMENT ON COLUMN tasks.estimated_duration_min IS 'Оценка длительности выполнения задачи в минутах (для родительских и подзадач)';

-- Index for parent_task_id (hierarchy queries)
CREATE INDEX IF NOT EXISTS idx_tasks_parent_task_id ON tasks (parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_task_type ON tasks (task_type);

-- ============================================
-- 4. task_dependencies (order between tasks: prerequisite -> dependent)
-- Semantics: child_task_id depends on parent_task_id (parent must complete first)
-- ============================================
CREATE TABLE IF NOT EXISTS task_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_task_id UUID NOT NULL REFERENCES tasks(id),
    child_task_id UUID NOT NULL REFERENCES tasks(id),
    dependency_type VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE task_dependencies IS 'Dependency: child_task_id depends on parent_task_id (parent must complete first). Used for execution order and parallel grouping.';

CREATE INDEX IF NOT EXISTS idx_task_deps_parent ON task_dependencies (parent_task_id);
CREATE INDEX IF NOT EXISTS idx_task_deps_child ON task_dependencies (child_task_id);

-- ============================================
-- 5. expert_specializations (category, proficiency, preferred_models)
-- ============================================
CREATE TABLE IF NOT EXISTS expert_specializations (
    expert_id UUID NOT NULL REFERENCES experts(id),
    category VARCHAR(50) NOT NULL,
    proficiency_score FLOAT DEFAULT 1.0,
    preferred_models JSONB,
    max_concurrent_tasks INTEGER DEFAULT 3,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (expert_id, category)
);

CREATE INDEX IF NOT EXISTS idx_expert_spec_category ON expert_specializations (category);
CREATE INDEX IF NOT EXISTS idx_expert_spec_proficiency ON expert_specializations (proficiency_score DESC);

-- Index on experts(is_active) if not already present (add_performance_optimizations may have created it)
CREATE INDEX IF NOT EXISTS idx_experts_active ON experts (is_active) WHERE is_active = TRUE;
