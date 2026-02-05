-- Migration: Add projects table (registry of allowed project_context for multi-tenant corporation)
-- Date: 2026-02-03
-- Purpose: Single source of truth for allowed projects; Victoria/Veronica load config from here.

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(500) NOT NULL,
    description TEXT,
    workspace_path VARCHAR(1000),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects (slug);
CREATE INDEX IF NOT EXISTS idx_projects_is_active ON projects (is_active) WHERE is_active = true;

-- Reuse existing trigger function if present
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Seed: default projects (idempotent)
INSERT INTO projects (slug, name, description, workspace_path, is_active)
VALUES
    ('atra-web-ide', 'ATRA Web IDE', 'Браузерная оболочка для ИИ-корпорации', '/workspace/atra-web-ide', true),
    ('atra', 'ATRA Trading System', 'Торговая система с ИИ-агентами', '/workspace/atra', true)
ON CONFLICT (slug) DO NOTHING;
