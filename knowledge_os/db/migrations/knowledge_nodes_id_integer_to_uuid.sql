-- Миграция: knowledge_nodes.id INTEGER -> UUID
-- Применять только к БД, где knowledge_nodes.id до сих пор integer (например из бэкапа).
-- После миграции тесты knowledge_graph/load e2e перестают скипаться (см. TESTING_FULL_SYSTEM.md).
-- Если knowledge_nodes.id уже UUID — блок не выполняет изменений (no-op).

DO $$
DECLARE
    kn_id_type text;
BEGIN
    SELECT data_type INTO kn_id_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'knowledge_nodes' AND column_name = 'id';

    IF kn_id_type IS NULL OR kn_id_type != 'integer' THEN
        RETURN; -- уже UUID или таблицы нет
    END IF;

    -- 1. Снять FK expert_discussions -> knowledge_nodes (если есть)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'expert_discussions') THEN
        ALTER TABLE expert_discussions DROP CONSTRAINT IF EXISTS expert_discussions_knowledge_node_id_fkey;
    END IF;

    -- 2. Маппинг старый id (integer) -> новый id (uuid)
    CREATE TEMP TABLE IF NOT EXISTS kn_id_map (old_id integer PRIMARY KEY, new_id uuid);
    TRUNCATE kn_id_map;
    INSERT INTO kn_id_map (old_id, new_id)
    SELECT id, gen_random_uuid() FROM knowledge_nodes;

    -- 3. Новая колонка в knowledge_nodes
    ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS id_new uuid;
    UPDATE knowledge_nodes SET id_new = m.new_id FROM kn_id_map m WHERE knowledge_nodes.id = m.old_id;

    -- 4. expert_discussions: перевести knowledge_node_id на uuid
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'expert_discussions' AND column_name = 'knowledge_node_id') THEN
        ALTER TABLE expert_discussions ADD COLUMN IF NOT EXISTS knowledge_node_id_uuid uuid;
        UPDATE expert_discussions ed SET knowledge_node_id_uuid = m.new_id
        FROM kn_id_map m WHERE ed.knowledge_node_id = m.old_id;
        ALTER TABLE expert_discussions DROP COLUMN IF EXISTS knowledge_node_id;
        ALTER TABLE expert_discussions RENAME COLUMN knowledge_node_id_uuid TO knowledge_node_id;
    END IF;

    -- 5. В knowledge_nodes: заменить id на id_new
    ALTER TABLE knowledge_nodes DROP CONSTRAINT IF EXISTS knowledge_nodes_pkey;
    ALTER TABLE knowledge_nodes DROP COLUMN id;
    ALTER TABLE knowledge_nodes RENAME COLUMN id_new TO id;
    ALTER TABLE knowledge_nodes ADD PRIMARY KEY (id);
    ALTER TABLE knowledge_nodes ALTER COLUMN id SET DEFAULT gen_random_uuid();

    -- 6. Вернуть FK expert_discussions (если колонка knowledge_node_id есть)
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'expert_discussions' AND column_name = 'knowledge_node_id') THEN
        ALTER TABLE expert_discussions
        ADD CONSTRAINT expert_discussions_knowledge_node_id_fkey
        FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes(id);
        CREATE INDEX IF NOT EXISTS idx_expert_discussions_knowledge_node_id
        ON expert_discussions (knowledge_node_id) WHERE knowledge_node_id IS NOT NULL;
    END IF;
END $$;
