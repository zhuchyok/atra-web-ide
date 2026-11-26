CREATE TABLE IF NOT EXISTS agent_message_schemas (
    verb VARCHAR(50) NOT NULL,
    version VARCHAR(10) NOT NULL DEFAULT '1.0',
    description TEXT,
    required_fields JSONB DEFAULT '[]',
    optional_fields JSONB DEFAULT '[]',
    max_payload_size INT DEFAULT 65536,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (verb, version)
);
