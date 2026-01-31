-- Миграция для расширения semantic_ai_cache с метриками роутинга
-- Singularity 5.0: Predictive & Adaptive Intelligence

-- Добавляем поля для tracking источника и качества ответа
ALTER TABLE semantic_ai_cache 
ADD COLUMN IF NOT EXISTS routing_source TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS performance_score FLOAT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS tokens_saved INTEGER DEFAULT 0;

-- Создаем индекс для быстрого поиска по routing_source
CREATE INDEX IF NOT EXISTS idx_semantic_cache_routing_source 
ON semantic_ai_cache(routing_source) 
WHERE routing_source IS NOT NULL;

-- Создаем индекс для поиска по performance_score
CREATE INDEX IF NOT EXISTS idx_semantic_cache_performance 
ON semantic_ai_cache(performance_score) 
WHERE performance_score IS NOT NULL;

-- Комментарии для документации
COMMENT ON COLUMN semantic_ai_cache.routing_source IS 'Источник ответа: mac|server|cloud';
COMMENT ON COLUMN semantic_ai_cache.performance_score IS 'Оценка качества ответа (0.0-1.0)';
COMMENT ON COLUMN semantic_ai_cache.tokens_saved IS 'Количество сэкономленных токенов';

