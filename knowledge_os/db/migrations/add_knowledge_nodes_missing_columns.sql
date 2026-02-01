-- Миграция: добавление недостающих колонок в knowledge_nodes
-- Исправляет ошибки дашборда: expert_consensus does not exist, source_ref, updated_at
-- Причина: текущая схема (из atra backup) отличается от ожидаемой init.sql

-- expert_consensus: результаты adversarial testing (используется в Иммунитет, adversarial_critic)
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS expert_consensus JSONB DEFAULT '{}';

-- source_ref: ссылка на файл или источник (seed_knowledge, smart_worker, server_knowledge_sync)
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS source_ref TEXT;

-- updated_at: для триггера и last_db_update на дашборде
ALTER TABLE knowledge_nodes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Триггер для updated_at (если ещё не существует)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_knowledge_nodes_updated_at ON knowledge_nodes;
CREATE TRIGGER update_knowledge_nodes_updated_at
    BEFORE UPDATE ON knowledge_nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Индекс для updated_at (last_db_update)
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_updated_at ON knowledge_nodes (updated_at DESC NULLS LAST);
