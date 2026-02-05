-- Fix: knowledge_nodes.id is INTEGER, expert_discussions.knowledge_node_id was UUID
-- This migration aligns expert_discussions with the actual knowledge_nodes schema.
-- Run: psql $DATABASE_URL -f fix_expert_discussions_knowledge_node_id_type.sql

-- 1. Drop FK constraint if exists
ALTER TABLE expert_discussions DROP CONSTRAINT IF EXISTS expert_discussions_knowledge_node_id_fkey;

-- 2. Drop old column (UUID type)
ALTER TABLE expert_discussions DROP COLUMN IF EXISTS knowledge_node_id;

-- 3. Add new column with correct type (INTEGER to match knowledge_nodes.id)
ALTER TABLE expert_discussions ADD COLUMN knowledge_node_id INTEGER REFERENCES knowledge_nodes(id);

-- 4. Index for joins
CREATE INDEX IF NOT EXISTS idx_expert_discussions_knowledge_node_id 
ON expert_discussions (knowledge_node_id) WHERE knowledge_node_id IS NOT NULL;
