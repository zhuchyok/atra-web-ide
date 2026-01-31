-- Migration: Add knowledge_links table for explicit knowledge graph
-- Дата: 2025-12-14
-- Версия: Singularity 3.7

-- Таблица для явных связей между знаниями
CREATE TABLE IF NOT EXISTS knowledge_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    link_type VARCHAR(50) NOT NULL, -- 'depends_on', 'contradicts', 'enhances', 'related_to', 'supersedes', 'part_of'
    strength FLOAT DEFAULT 1.0, -- Сила связи (0.0 - 1.0)
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Уникальность: одна связь одного типа между двумя узлами
    UNIQUE(source_node_id, target_node_id, link_type),
    
    -- Проверка: узел не может быть связан сам с собой
    CHECK (source_node_id != target_node_id)
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_knowledge_links_source ON knowledge_links (source_node_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_links_target ON knowledge_links (target_node_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_links_type ON knowledge_links (link_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_links_strength ON knowledge_links (strength DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_links_metadata ON knowledge_links USING GIN (metadata);

-- Композитный индекс для быстрого поиска связей
CREATE INDEX IF NOT EXISTS idx_knowledge_links_source_type 
    ON knowledge_links (source_node_id, link_type);

-- Триггер для обновления updated_at
CREATE TRIGGER update_knowledge_links_updated_at
    BEFORE UPDATE ON knowledge_links
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Представление для удобного доступа к связям с информацией об узлах
CREATE OR REPLACE VIEW knowledge_graph_view AS
SELECT 
    kl.id as link_id,
    kl.source_node_id,
    kl.target_node_id,
    kl.link_type,
    kl.strength,
    kl.metadata as link_metadata,
    kl.created_at as link_created_at,
    -- Информация об исходном узле
    sn.content as source_content,
    sn.confidence_score as source_confidence,
    sd.name as source_domain,
    -- Информация о целевом узле
    tn.content as target_content,
    tn.confidence_score as target_confidence,
    td.name as target_domain
FROM knowledge_links kl
JOIN knowledge_nodes sn ON kl.source_node_id = sn.id
JOIN knowledge_nodes tn ON kl.target_node_id = tn.id
LEFT JOIN domains sd ON sn.domain_id = sd.id
LEFT JOIN domains td ON tn.domain_id = td.id;

-- Функция для автоматического создания обратных связей (для двунаправленных типов)
CREATE OR REPLACE FUNCTION create_bidirectional_link()
RETURNS TRIGGER AS $$
BEGIN
    -- Для типов 'related_to' и 'enhances' создаем обратную связь
    IF NEW.link_type IN ('related_to', 'enhances') THEN
        INSERT INTO knowledge_links (source_node_id, target_node_id, link_type, strength, metadata)
        VALUES (NEW.target_node_id, NEW.source_node_id, NEW.link_type, NEW.strength, NEW.metadata)
        ON CONFLICT (source_node_id, target_node_id, link_type) DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического создания обратных связей
CREATE TRIGGER create_bidirectional_link_trigger
    AFTER INSERT ON knowledge_links
    FOR EACH ROW
    WHEN (NEW.link_type IN ('related_to', 'enhances'))
    EXECUTE FUNCTION create_bidirectional_link();

-- Функция для поиска связанных узлов
CREATE OR REPLACE FUNCTION get_related_nodes(
    p_node_id UUID,
    link_types TEXT[] DEFAULT ARRAY['depends_on', 'enhances', 'related_to'],
    max_depth INTEGER DEFAULT 2,
    min_strength FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    node_id UUID,
    content TEXT,
    domain_name VARCHAR,
    link_type VARCHAR,
    depth INTEGER,
    path UUID[]
) AS $$
BEGIN
    RETURN QUERY
    WITH RECURSIVE knowledge_path AS (
        -- Базовый случай: начальный узел
        SELECT 
            kl.target_node_id as node_id,
            kl.link_type,
            1 as depth,
            ARRAY[kl.source_node_id, kl.target_node_id] as path
        FROM knowledge_links kl
        WHERE kl.source_node_id = p_node_id
          AND kl.link_type = ANY(link_types)
          AND kl.strength >= min_strength
        
        UNION ALL
        
        -- Рекурсивный случай: связанные узлы
        SELECT 
            kl.target_node_id as node_id,
            kl.link_type,
            kp.depth + 1,
            kp.path || kl.target_node_id
        FROM knowledge_links kl
        JOIN knowledge_path kp ON kl.source_node_id = kp.node_id
        WHERE kp.depth < max_depth
          AND kl.link_type = ANY(link_types)
          AND kl.strength >= min_strength
          AND NOT (kl.target_node_id = ANY(kp.path)) -- Избегаем циклов
    )
    SELECT DISTINCT
        kp.node_id,
        kn.content,
        d.name as domain_name,
        kp.link_type,
        kp.depth,
        kp.path
    FROM knowledge_path kp
    JOIN knowledge_nodes kn ON kp.node_id = kn.id
    LEFT JOIN domains d ON kn.domain_id = d.id
    ORDER BY kp.depth, kp.link_type;
END;
$$ LANGUAGE plpgsql;

-- Комментарии для документации
COMMENT ON TABLE knowledge_links IS 'Явные связи между узлами знаний для построения графа знаний';
COMMENT ON COLUMN knowledge_links.link_type IS 'Тип связи: depends_on, contradicts, enhances, related_to, supersedes, part_of';
COMMENT ON COLUMN knowledge_links.strength IS 'Сила связи от 0.0 до 1.0, где 1.0 - максимальная связь';
COMMENT ON VIEW knowledge_graph_view IS 'Представление для удобного доступа к графу знаний с информацией об узлах';
COMMENT ON FUNCTION get_related_nodes IS 'Рекурсивная функция для поиска связанных узлов с ограничением глубины';

