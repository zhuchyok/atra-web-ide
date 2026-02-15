-- Fix: expert_discussions.knowledge_node_id должен совпадать по типу с knowledge_nodes.id
-- Условно: если knowledge_nodes.id = UUID — колонка UUID; если INTEGER — INTEGER (бэкап/legacy).
-- После этого apply_migrations не падает ни на свежей БД (init.sql = UUID), ни на старой (integer).

DO $$
DECLARE
    kn_id_type text;
BEGIN
    -- Таблица может быть создана add_tasks_table с knowledge_node_id UUID; или ещё не создана
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'expert_discussions') THEN
        RETURN;
    END IF;

    SELECT data_type INTO kn_id_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'knowledge_nodes' AND column_name = 'id';

    -- Снять FK и старую колонку (если есть)
    ALTER TABLE expert_discussions DROP CONSTRAINT IF EXISTS expert_discussions_knowledge_node_id_fkey;
    ALTER TABLE expert_discussions DROP COLUMN IF EXISTS knowledge_node_id;

    IF kn_id_type = 'uuid' THEN
        ALTER TABLE expert_discussions ADD COLUMN knowledge_node_id UUID REFERENCES knowledge_nodes(id);
    ELSIF kn_id_type = 'integer' THEN
        ALTER TABLE expert_discussions ADD COLUMN knowledge_node_id INTEGER REFERENCES knowledge_nodes(id);
    ELSE
        -- тип не uuid и не integer — не трогаем
        RETURN;
    END IF;

    CREATE INDEX IF NOT EXISTS idx_expert_discussions_knowledge_node_id
    ON expert_discussions (knowledge_node_id) WHERE knowledge_node_id IS NOT NULL;
END $$;
