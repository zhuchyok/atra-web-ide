-- Добавить колонки организационной структуры в experts (для organizational_structure).
-- Требуется для работы organizational_structure.get_full_structure().
-- Применяется автоматически при запуске Enhanced Orchestrator (Phase 0.5)
-- или вручную: psql $DATABASE_URL -f knowledge_os/db/migrations/add_experts_organizational_columns.sql

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'experts' AND column_name = 'organizational_unit_id'
    ) THEN
        ALTER TABLE experts ADD COLUMN organizational_unit_id INTEGER DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'experts' AND column_name = 'is_manager'
    ) THEN
        ALTER TABLE experts ADD COLUMN is_manager BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'experts' AND column_name = 'manages_unit_id'
    ) THEN
        ALTER TABLE experts ADD COLUMN manages_unit_id INTEGER DEFAULT 0;
    END IF;
END $$;

-- Индекс для выборки по подразделению (опционально)
CREATE INDEX IF NOT EXISTS idx_experts_organizational_unit_id ON experts (organizational_unit_id) WHERE organizational_unit_id > 0;
CREATE INDEX IF NOT EXISTS idx_experts_is_manager ON experts (is_manager) WHERE is_manager = TRUE;
