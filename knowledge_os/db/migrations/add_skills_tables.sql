-- Migration: Add skills tables for Skill Registry
-- Date: 2026-01-26
-- Version: Singularity 9.0

-- Skills table - реестр всех skills
CREATE TABLE IF NOT EXISTS skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    category VARCHAR(100),
    version VARCHAR(50) DEFAULT '1.0.0',
    source VARCHAR(50) NOT NULL, -- 'builtin', 'managed', 'workspace', 'discovered', 'clawdhub'
    skill_path TEXT NOT NULL, -- Путь к SKILL.md файлу
    metadata JSONB DEFAULT '{}', -- AgentSkills metadata (bins, env, config)
    instructions TEXT, -- Инструкции из SKILL.md
    handler_path TEXT, -- Путь к handler.py (если есть)
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Skill usage statistics - статистика использования skills
CREATE TABLE IF NOT EXISTS skill_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    execution_time_ms INTEGER, -- Время выполнения в миллисекундах
    error_message TEXT,
    context JSONB DEFAULT '{}' -- Контекст использования (event_id, task_id, etc.)
);

-- Skill metadata cache - кэш метаданных skills для быстрой загрузки
CREATE TABLE IF NOT EXISTS skill_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    metadata_key VARCHAR(255) NOT NULL, -- 'bins', 'env', 'config', 'homepage', 'emoji'
    metadata_value JSONB NOT NULL,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(skill_id, metadata_key)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category);
CREATE INDEX IF NOT EXISTS idx_skills_source ON skills(source);
CREATE INDEX IF NOT EXISTS idx_skills_enabled ON skills(enabled);
CREATE INDEX IF NOT EXISTS idx_skills_created_at ON skills(created_at);

CREATE INDEX IF NOT EXISTS idx_skill_usage_skill_id ON skill_usage(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_usage_used_at ON skill_usage(used_at);
CREATE INDEX IF NOT EXISTS idx_skill_usage_success ON skill_usage(success);

CREATE INDEX IF NOT EXISTS idx_skill_metadata_skill_id ON skill_metadata(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_metadata_key ON skill_metadata(metadata_key);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_skills_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_skills_updated_at
    BEFORE UPDATE ON skills
    FOR EACH ROW
    EXECUTE FUNCTION update_skills_updated_at();

-- Comments
COMMENT ON TABLE skills IS 'Реестр всех skills в формате AgentSkills';
COMMENT ON TABLE skill_usage IS 'Статистика использования skills для аналитики и оптимизации';
COMMENT ON TABLE skill_metadata IS 'Кэш метаданных skills для быстрой загрузки';

COMMENT ON COLUMN skills.source IS 'Источник skill: builtin (встроенные), managed (установленные), workspace (проектные), discovered (автообнаруженные), clawdhub (из ClawdHub)';
COMMENT ON COLUMN skills.metadata IS 'Метаданные в формате AgentSkills: {"clawdbot": {"requires": {"bins": [...], "env": [...]}, "emoji": "📝"}}';
COMMENT ON COLUMN skills.skill_path IS 'Путь к SKILL.md файлу (относительно корня проекта или абсолютный)';
