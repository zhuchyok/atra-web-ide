-- Миграция для версионирования системы

CREATE TABLE IF NOT EXISTS system_versions (
    id SERIAL PRIMARY KEY,
    version TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL, -- 'stable', 'beta', 'dev'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deployed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS version_migrations (
    id SERIAL PRIMARY KEY,
    version TEXT NOT NULL,
    migration_name TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL, -- 'success', 'failed', 'rolled_back'
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_system_versions_status ON system_versions(status);
CREATE INDEX IF NOT EXISTS idx_version_migrations_version ON version_migrations(version);

COMMENT ON TABLE system_versions IS 'Версии системы Singularity';
COMMENT ON TABLE version_migrations IS 'История применения миграций версий';

