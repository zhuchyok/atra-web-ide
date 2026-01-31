-- Migration: Add contextual memory tables for enhanced learning
-- Дата: 2025-12-14
-- Версия: Singularity 3.8

-- Таблица для контекстной памяти (успешные паттерны)
CREATE TABLE IF NOT EXISTS contextual_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_type VARCHAR(50) NOT NULL, -- 'query_pattern', 'response_pattern', 'interaction_pattern'
    context_hash VARCHAR(64) NOT NULL, -- SHA256 хеш контекста для быстрого поиска
    pattern_data JSONB NOT NULL, -- Данные паттерна (запрос, ответ, метрики)
    success_score FLOAT DEFAULT 0.0, -- Оценка успешности (0.0 - 1.0)
    usage_count INTEGER DEFAULT 0, -- Количество использований
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(context_hash, pattern_type)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_contextual_patterns_type ON contextual_patterns (pattern_type);
CREATE INDEX IF NOT EXISTS idx_contextual_patterns_success ON contextual_patterns (success_score DESC);
CREATE INDEX IF NOT EXISTS idx_contextual_patterns_usage ON contextual_patterns (usage_count DESC);
CREATE INDEX IF NOT EXISTS idx_contextual_patterns_hash ON contextual_patterns (context_hash);
CREATE INDEX IF NOT EXISTS idx_contextual_patterns_data ON contextual_patterns USING GIN (pattern_data);

-- Таблица для персонализации (предпочтения пользователей)
CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_identifier VARCHAR(255) NOT NULL, -- Идентификатор пользователя (может быть анонимным)
    preference_type VARCHAR(50) NOT NULL, -- 'domain_preference', 'expert_preference', 'response_style'
    preference_key VARCHAR(255) NOT NULL, -- Ключ предпочтения
    preference_value JSONB NOT NULL, -- Значение предпочтения
    confidence FLOAT DEFAULT 0.5, -- Уверенность в предпочтении
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_identifier, preference_type, preference_key)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences (user_identifier);
CREATE INDEX IF NOT EXISTS idx_user_preferences_type ON user_preferences (preference_type);
CREATE INDEX IF NOT EXISTS idx_user_preferences_value ON user_preferences USING GIN (preference_value);

-- Таблица для прогнозирования потребностей
CREATE TABLE IF NOT EXISTS need_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_identifier VARCHAR(255),
    predicted_domain VARCHAR(255),
    predicted_topic TEXT,
    confidence FLOAT DEFAULT 0.0,
    prediction_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP WITH TIME ZONE, -- Когда предсказание подтвердилось
    is_validated BOOLEAN DEFAULT FALSE
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_need_predictions_user ON need_predictions (user_identifier);
CREATE INDEX IF NOT EXISTS idx_need_predictions_domain ON need_predictions (predicted_domain);
CREATE INDEX IF NOT EXISTS idx_need_predictions_validated ON need_predictions (is_validated);

-- Таблица для адаптивного обучения (обратная связь)
CREATE TABLE IF NOT EXISTS adaptive_learning_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_log_id UUID, -- Связь с interaction_logs (без FK из-за возможного несоответствия типов)
    expert_id UUID REFERENCES experts(id),
    learning_type VARCHAR(50) NOT NULL, -- 'feedback_learning', 'pattern_learning', 'context_learning'
    learned_insight TEXT NOT NULL,
    impact_score FLOAT DEFAULT 0.0, -- Влияние на качество ответов
    applied_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_adaptive_learning_expert ON adaptive_learning_logs (expert_id);
CREATE INDEX IF NOT EXISTS idx_adaptive_learning_type ON adaptive_learning_logs (learning_type);
CREATE INDEX IF NOT EXISTS idx_adaptive_learning_impact ON adaptive_learning_logs (impact_score DESC);

-- Триггеры для updated_at (с проверкой существования)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_contextual_patterns_updated_at') THEN
        CREATE TRIGGER update_contextual_patterns_updated_at
            BEFORE UPDATE ON contextual_patterns
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_user_preferences_updated_at') THEN
        CREATE TRIGGER update_user_preferences_updated_at
            BEFORE UPDATE ON user_preferences
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Функция для извлечения контекста из запроса
CREATE OR REPLACE FUNCTION extract_context_hash(
    query_text TEXT,
    domain_name VARCHAR DEFAULT NULL,
    expert_name VARCHAR DEFAULT NULL
) RETURNS VARCHAR(64) AS $$
BEGIN
    -- Простой хеш контекста (в реальности можно использовать более сложную логику)
    RETURN encode(digest(
        COALESCE(query_text, '') || 
        COALESCE(domain_name, '') || 
        COALESCE(expert_name, ''),
        'sha256'
    ), 'hex');
END;
$$ LANGUAGE plpgsql;

-- Функция для поиска похожих паттернов
CREATE OR REPLACE FUNCTION find_similar_patterns(
    context_hash VARCHAR(64),
    pattern_type VARCHAR(50),
    min_success_score FLOAT DEFAULT 0.7,
    limit_count INTEGER DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    pattern_data JSONB,
    success_score FLOAT,
    usage_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cp.id,
        cp.pattern_data,
        cp.success_score,
        cp.usage_count
    FROM contextual_patterns cp
    WHERE cp.pattern_type = pattern_type
      AND cp.success_score >= min_success_score
      AND cp.context_hash != context_hash  -- Исключаем текущий паттерн
    ORDER BY cp.success_score DESC, cp.usage_count DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Комментарии
COMMENT ON TABLE contextual_patterns IS 'Контекстная память успешных паттернов взаимодействия';
COMMENT ON TABLE user_preferences IS 'Персонализация: предпочтения пользователей';
COMMENT ON TABLE need_predictions IS 'Прогнозирование потребностей пользователей';
COMMENT ON TABLE adaptive_learning_logs IS 'Логи адаптивного обучения на основе обратной связи';

