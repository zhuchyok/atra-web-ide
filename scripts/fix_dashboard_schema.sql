-- Миграция: добавить usage_count и is_verified в knowledge_nodes
-- Запуск: docker exec -i knowledge_postgres psql -U admin -d knowledge_os < scripts/fix_dashboard_schema.sql
-- или: psql postgresql://admin:secret@localhost:5432/knowledge_os -f scripts/fix_dashboard_schema.sql

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'knowledge_nodes' AND column_name = 'usage_count'
    ) THEN
        ALTER TABLE knowledge_nodes ADD COLUMN usage_count INTEGER DEFAULT 0;
        RAISE NOTICE 'usage_count добавлен';
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'knowledge_nodes' AND column_name = 'is_verified'
    ) THEN
        ALTER TABLE knowledge_nodes ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'is_verified добавлен';
    END IF;
END $$;
