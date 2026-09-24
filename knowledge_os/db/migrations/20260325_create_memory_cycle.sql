-- Migration: Create knowledge_archive and Safe Vector Pruning (Memory Cycle)
-- Singularity 24.0: Safe Vector Pruning

-- 1. Create knowledge_archive (schema identical to knowledge_nodes)
CREATE TABLE IF NOT EXISTS knowledge_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding vector(768), -- Assuming 768 dims based on migrations
    metadata JSONB DEFAULT '{}',
    usage_count INTEGER DEFAULT 0,
    is_verified BOOLEAN DEFAULT FALSE,
    project_context TEXT,
    expert_consensus JSONB DEFAULT '{}',
    source_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    archived_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Add usage_count to knowledge_nodes if not exists
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS usage_count INTEGER DEFAULT 0;
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;

-- 3. Soft Delete Procedure: Move nodes with usage_count = 0 older than 30 days to archive
-- IMPORTANT: Exclude is_verified = true, memory_crystals, and domain_summary
CREATE OR REPLACE FUNCTION prune_knowledge_nodes()
RETURNS INTEGER AS $$
DECLARE
    moved_count INTEGER;
BEGIN
    WITH moved_rows AS (
        DELETE FROM knowledge_nodes
        WHERE usage_count = 0
          AND created_at < NOW() - INTERVAL '30 days'
          AND is_verified = FALSE
          AND (metadata->>'type' IS NULL OR metadata->>'type' NOT IN ('memory_crystal', 'domain_summary'))
        RETURNING *
    )
    INSERT INTO knowledge_archive (id, content, embedding, metadata, usage_count, is_verified, project_context, expert_consensus, source_ref, created_at, updated_at)
    SELECT id, content, embedding, metadata, usage_count, is_verified, project_context, expert_consensus, source_ref, created_at, updated_at
    FROM moved_rows;

    GET DIAGNOSTICS moved_count = ROW_COUNT;
    RETURN moved_count;
END;
$$ LANGUAGE plpgsql;
