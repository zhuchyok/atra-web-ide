-- Migration: Create memory_crystals table
-- Singularity 23.0: Memory Crystals & U-Shape Context

CREATE TABLE IF NOT EXISTS memory_crystals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_context TEXT NOT NULL,
    crystal_type TEXT NOT NULL, -- 'decision', 'parameter', 'milestone', 'fact'
    content TEXT NOT NULL,
    confidence_score FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast retrieval by project
CREATE INDEX IF NOT EXISTS idx_crystals_project ON memory_crystals(project_context);

-- Initial crystals for current project state
INSERT INTO memory_crystals (project_context, crystal_type, content, metadata)
VALUES 
('atra-web-ide', 'parameter', 'Database Port: 6432 (PgBouncer)', '{"source": "manual_init"}'),
('atra-web-ide', 'decision', 'Implemented Smart Task Throttling & Deduplication in v37', '{"source": "manual_init"}'),
('atra-web-ide', 'decision', 'Deep Memory (Hierarchical RAG) integrated in v35', '{"source": "manual_init"}')
ON CONFLICT DO NOTHING;
