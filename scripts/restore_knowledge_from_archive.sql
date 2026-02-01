-- Восстановление узлов из архива (без embedding — archive 384-dim, knowledge_nodes 768-dim)
-- Запуск: docker cp scripts/restore_knowledge_from_archive.sql atra-web-ide-backend:/tmp/ && docker exec knowledge_postgres psql -U admin -d knowledge_os -f /tmp/restore_knowledge_from_archive.sql
-- Локально: psql postgresql://admin:secret@localhost:5432/knowledge_os -f scripts/restore_knowledge_from_archive.sql

INSERT INTO knowledge_nodes (content, metadata, confidence_score, is_verified, usage_count, created_at)
SELECT content, COALESCE(metadata, '{}'), COALESCE(confidence_score, 0.5), COALESCE(is_verified, false), COALESCE(usage_count, 0), created_at
FROM knowledge_nodes_archive;
