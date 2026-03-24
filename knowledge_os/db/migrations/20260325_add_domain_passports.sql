-- Insert initial domain summaries for core domains
INSERT INTO knowledge_nodes (domain_id, content, confidence_score, is_verified, metadata)
SELECT 
    id as domain_id,
    'Архитектурный паспорт домена ' || name || '. Стандарты: 12-Factor, SOLID, KISS. Текущий статус: 10/10.' as content,
    1.0 as confidence_score,
    true as is_verified,
    jsonb_build_object('type', 'domain_summary', 'source', 'system_init', 'domain_name', name) as metadata
FROM domains
ON CONFLICT DO NOTHING;
