-- Migration: Add tasks table with priority support
-- Date: 2025-12-14
-- Version: Singularity 3.1

-- Tasks table with priority and workload balancing
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, completed, failed, cancelled
    priority VARCHAR(20) DEFAULT 'medium', -- urgent, high, medium, low
    assignee_expert_id UUID REFERENCES experts(id),
    creator_expert_id UUID REFERENCES experts(id),
    domain_id UUID REFERENCES domains(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_duration_minutes INTEGER, -- Estimated time to complete
    actual_duration_minutes INTEGER -- Actual time taken
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks (assignee_expert_id);
CREATE INDEX IF NOT EXISTS idx_tasks_creator ON tasks (creator_expert_id);
CREATE INDEX IF NOT EXISTS idx_tasks_domain ON tasks (domain_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks (created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_metadata ON tasks USING GIN (metadata);

-- Composite index for task selection queries
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks (status, priority, created_at);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS update_tasks_updated_at ON tasks;
CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add usage_count to knowledge_nodes if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'knowledge_nodes' AND column_name = 'usage_count'
    ) THEN
        ALTER TABLE knowledge_nodes ADD COLUMN usage_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- Add is_verified to knowledge_nodes if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'knowledge_nodes' AND column_name = 'is_verified'
    ) THEN
        ALTER TABLE knowledge_nodes ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Add department to experts if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'experts' AND column_name = 'department'
    ) THEN
        ALTER TABLE experts ADD COLUMN department VARCHAR(255);
    END IF;
END $$;

-- Add last_learned_at to experts if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'experts' AND column_name = 'last_learned_at'
    ) THEN
        ALTER TABLE experts ADD COLUMN last_learned_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Add version to experts if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'experts' AND column_name = 'version'
    ) THEN
        ALTER TABLE experts ADD COLUMN version INTEGER DEFAULT 1;
    END IF;
END $$;

-- Add notifications table if not exists
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message TEXT NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add expert_discussions table if not exists
CREATE TABLE IF NOT EXISTS expert_discussions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_node_id UUID REFERENCES knowledge_nodes(id),
    expert_ids UUID[],
    topic TEXT,
    consensus_summary TEXT,
    status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add system_metrics table if not exists (for monitoring)
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metrics JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics (timestamp);

