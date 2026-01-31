-- Миграция для добавления TTL и приоритетов в semantic_ai_cache
-- Singularity 8.0: Performance Optimization

-- Добавляем колонки для TTL и приоритетов
ALTER TABLE semantic_ai_cache 
ADD COLUMN IF NOT EXISTS ttl_seconds INTEGER DEFAULT 86400, -- 24 часа по умолчанию
ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'medium' CHECK (priority IN ('critical', 'high', 'medium', 'low')),
ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Создаем индекс для быстрого поиска по expires_at
CREATE INDEX IF NOT EXISTS idx_semantic_cache_expires_at ON semantic_ai_cache(expires_at) WHERE expires_at IS NOT NULL;

-- Создаем индекс для поиска по приоритету
CREATE INDEX IF NOT EXISTS idx_semantic_cache_priority ON semantic_ai_cache(priority);

-- Обновляем существующие записи: устанавливаем expires_at на основе created_at и ttl_seconds
UPDATE semantic_ai_cache 
SET expires_at = COALESCE(created_at, CURRENT_TIMESTAMP) + INTERVAL '1 second' * COALESCE(ttl_seconds, 86400)
WHERE expires_at IS NULL;

-- Функция для автоматического обновления expires_at при вставке
CREATE OR REPLACE FUNCTION update_cache_expires_at()
RETURNS TRIGGER AS $$
BEGIN
    -- Если expires_at не установлен, вычисляем на основе created_at и ttl_seconds
    IF NEW.expires_at IS NULL THEN
        NEW.expires_at = COALESCE(NEW.created_at, CURRENT_TIMESTAMP) + INTERVAL '1 second' * COALESCE(NEW.ttl_seconds, 86400);
    END IF;
    
    -- Если created_at не установлен, устанавливаем текущее время
    IF NEW.created_at IS NULL THEN
        NEW.created_at = CURRENT_TIMESTAMP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического обновления expires_at
DROP TRIGGER IF EXISTS trigger_update_cache_expires_at ON semantic_ai_cache;
CREATE TRIGGER trigger_update_cache_expires_at
    BEFORE INSERT OR UPDATE ON semantic_ai_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_cache_expires_at();

-- Комментарии к колонкам
COMMENT ON COLUMN semantic_ai_cache.ttl_seconds IS 'Время жизни кэша в секундах';
COMMENT ON COLUMN semantic_ai_cache.priority IS 'Приоритет кэша: critical (7 дней), high (3 дня), medium (1 день), low (6 часов)';
COMMENT ON COLUMN semantic_ai_cache.expires_at IS 'Время истечения кэша (автоматически вычисляется)';
COMMENT ON COLUMN semantic_ai_cache.created_at IS 'Время создания записи';

