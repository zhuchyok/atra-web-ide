-- После миграции knowledge_nodes_id_integer_to_uuid колонка id (UUID) не имела DEFAULT.
-- Устанавливаем DEFAULT gen_random_uuid() для INSERT без явного id (тесты и приложение).
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'knowledge_nodes' AND column_name = 'id'
        AND data_type = 'uuid'
    ) THEN
        ALTER TABLE knowledge_nodes ALTER COLUMN id SET DEFAULT gen_random_uuid();
    END IF;
END $$;
