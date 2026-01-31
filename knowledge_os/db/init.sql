-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Table for Expert Personas (Migration from atra)
CREATE TABLE IF NOT EXISTS experts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    role VARCHAR(255) NOT NULL,
    department VARCHAR(255),
    system_prompt TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for Knowledge Domains
CREATE TABLE IF NOT EXISTS domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Central Knowledge Table (Adaptive)
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_id UUID REFERENCES domains(id),
    content TEXT NOT NULL,
    embedding vector(768), -- Updated for nomic-embed-text
    metadata JSONB DEFAULT '{}',
    confidence_score FLOAT DEFAULT 1.0,
    is_verified BOOLEAN DEFAULT FALSE,
    source_ref TEXT, -- Reference to the file or conversation
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for Tasks (NEW)
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, completed, failed
    priority VARCHAR(50) DEFAULT 'medium', -- low, medium, high, urgent
    assignee_expert_id UUID REFERENCES experts(id),
    creator_expert_id UUID REFERENCES experts(id),
    domain_id UUID REFERENCES domains(id),
    metadata JSONB DEFAULT '{}',
    result TEXT,
    actual_duration_minutes INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Feedback and Interaction Logs
CREATE TABLE IF NOT EXISTS interaction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id UUID REFERENCES experts(id),
    user_query TEXT,
    assistant_response TEXT,
    feedback_score INTEGER, -- 1 for like, -1 for dislike
    feedback_text TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance (based on performance_guide.md)
CREATE INDEX idx_knowledge_domain ON knowledge_nodes (domain_id);
CREATE INDEX idx_knowledge_metadata ON knowledge_nodes USING GIN (metadata);
CREATE INDEX idx_knowledge_embedding ON knowledge_nodes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_knowledge_nodes_updated_at
    BEFORE UPDATE ON knowledge_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

