-- Удаление домена web_redesign_oknabalkony52 из карты разума и БД.
-- Применение: psql $DATABASE_URL -f knowledge_os/db/migrations/remove_web_redesign_oknabalkony52_domain.sql

-- 1. Создать домен "Web & Product" если его нет
INSERT INTO domains (name, description)
VALUES ('Web & Product', 'Web, UX/UI, Product design')
ON CONFLICT (name) DO NOTHING;

-- 2. Перепривязать knowledge_nodes с web_redesign_oknabalkony52 на Web & Product
UPDATE knowledge_nodes kn
SET domain_id = (SELECT id FROM domains WHERE name = 'Web & Product' LIMIT 1)
WHERE domain_id = (SELECT id FROM domains WHERE name = 'web_redesign_oknabalkony52' LIMIT 1);

-- 3. Перепривязать experts.domain_id (если колонка есть)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'experts' AND column_name = 'domain_id'
  ) THEN
    UPDATE experts e
    SET domain_id = (SELECT id FROM domains WHERE name = 'Web & Product' LIMIT 1)
    WHERE e.domain_id = (SELECT id FROM domains WHERE name = 'web_redesign_oknabalkony52' LIMIT 1);
  END IF;
END $$;

-- 4. Перепривязать tasks.domain_id (если колонка есть)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'tasks' AND column_name = 'domain_id'
  ) THEN
    UPDATE tasks t
    SET domain_id = (SELECT id FROM domains WHERE name = 'Web & Product' LIMIT 1)
    WHERE t.domain_id = (SELECT id FROM domains WHERE name = 'web_redesign_oknabalkony52' LIMIT 1);
  END IF;
END $$;

-- 5. Удалить домен web_redesign_oknabalkony52
DELETE FROM domains WHERE name = 'web_redesign_oknabalkony52';
