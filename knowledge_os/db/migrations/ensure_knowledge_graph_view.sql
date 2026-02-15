-- Создать представление knowledge_graph_view, если отсутствует (миграция add_knowledge_links_table могла не дойти до VIEW из-за триггера).
CREATE OR REPLACE VIEW knowledge_graph_view AS
SELECT 
    kl.id as link_id,
    kl.source_node_id,
    kl.target_node_id,
    kl.link_type,
    kl.strength,
    kl.metadata as link_metadata,
    kl.created_at as link_created_at,
    sn.content as source_content,
    sn.confidence_score as source_confidence,
    sd.name as source_domain,
    tn.content as target_content,
    tn.confidence_score as target_confidence,
    td.name as target_domain
FROM knowledge_links kl
JOIN knowledge_nodes sn ON kl.source_node_id = sn.id
JOIN knowledge_nodes tn ON kl.target_node_id = tn.id
LEFT JOIN domains sd ON sn.domain_id = sd.id
LEFT JOIN domains td ON tn.domain_id = td.id;
