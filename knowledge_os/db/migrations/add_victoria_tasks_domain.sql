-- Самообучение Виктории (Victoria Tasks): домен для записей _learn_from_task.
-- Без этого домена записи пишутся с domain_id NULL и не попадают в RAG/планирование.
-- Применение: при старте Knowledge OS или вручную psql $DATABASE_URL -f ...

-- 1. Создать домен victoria_tasks если его нет
INSERT INTO domains (name, description)
VALUES ('victoria_tasks', 'Victoria self-learning: completed task outcomes and insights')
ON CONFLICT (name) DO NOTHING;

-- 2. Перенести уже записанные «обучения» (domain_id IS NULL, эксперт Виктория) в этот домен
UPDATE knowledge_nodes kn
SET domain_id = (SELECT id FROM domains WHERE name = 'victoria_tasks' LIMIT 1)
WHERE kn.domain_id IS NULL
  AND kn.metadata IS NOT NULL
  AND kn.metadata->>'expert' = 'Виктория';
