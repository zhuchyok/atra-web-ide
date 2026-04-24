-- [SINGULARITY 28.0] Migration: Knowledge Edges for GraphRAG
CREATE TABLE IF NOT EXISTS knowledge_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id INTEGER REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL, -- 'influences', 'contradicts', 'supports', 'part_of'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_edges_source ON knowledge_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_target ON knowledge_edges(target_id);
