-- Добавить domain_id в experts для workers (worker.py, smart_worker_v3, streaming_worker, force_worker).
-- Без этой миграции workers падают: SELECT domain_id FROM experts.
-- Применение: psql $DATABASE_URL -f knowledge_os/db/migrations/add_experts_domain_id.sql

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'experts' AND column_name = 'domain_id'
    ) THEN
        ALTER TABLE experts ADD COLUMN domain_id UUID REFERENCES domains(id);
    END IF;
END $$;

-- Заполнить domain_id из department (домен с тем же именем)
UPDATE experts e
SET domain_id = (SELECT id FROM domains d WHERE d.name = e.department LIMIT 1)
WHERE domain_id IS NULL AND e.department IS NOT NULL;

-- Индекс для производительности
CREATE INDEX IF NOT EXISTS idx_experts_domain_id ON experts(domain_id) WHERE domain_id IS NOT NULL;
