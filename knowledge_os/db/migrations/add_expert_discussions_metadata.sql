-- War Room (Tactical War Room) хранит session_id, log, severity в metadata
ALTER TABLE expert_discussions ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_expert_discussions_metadata ON expert_discussions USING GIN (metadata) WHERE metadata != '{}'::jsonb;
