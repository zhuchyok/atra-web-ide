-- Migration: Add multilanguage support
-- Дата: 2025-12-14
-- Версия: Singularity 4.5

-- Таблица для переводов знаний
CREATE TABLE IF NOT EXISTS knowledge_translations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_node_id UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    language_code VARCHAR(10) NOT NULL, -- 'en', 'ru', 'es', 'fr', 'de', 'zh', 'ja', etc.
    translated_content TEXT NOT NULL,
    translation_confidence FLOAT DEFAULT 1.0,
    translation_source VARCHAR(50) DEFAULT 'auto', -- 'auto', 'manual', 'api'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(knowledge_node_id, language_code)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_knowledge_translations_node ON knowledge_translations (knowledge_node_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_translations_lang ON knowledge_translations (language_code);
CREATE INDEX IF NOT EXISTS idx_knowledge_translations_confidence ON knowledge_translations (translation_confidence DESC);

-- Таблица для локализации интерфейса
CREATE TABLE IF NOT EXISTS ui_translations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    language_code VARCHAR(10) NOT NULL,
    translation_key VARCHAR(255) NOT NULL,
    translation_value TEXT NOT NULL,
    context VARCHAR(100), -- 'dashboard', 'api', 'telegram', etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(language_code, translation_key, context)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_ui_translations_lang ON ui_translations (language_code);
CREATE INDEX IF NOT EXISTS idx_ui_translations_key ON ui_translations (translation_key);
CREATE INDEX IF NOT EXISTS idx_ui_translations_context ON ui_translations (context);

-- Таблица для языковых настроек пользователей
CREATE TABLE IF NOT EXISTS user_language_preferences (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    preferred_language VARCHAR(10) DEFAULT 'en',
    interface_language VARCHAR(10) DEFAULT 'en',
    search_language VARCHAR(10) DEFAULT 'auto', -- 'auto' = автоматическое определение
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (user_id)
);

-- Триггеры
CREATE TRIGGER update_knowledge_translations_updated_at
    BEFORE UPDATE ON knowledge_translations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ui_translations_updated_at
    BEFORE UPDATE ON ui_translations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_language_preferences_updated_at
    BEFORE UPDATE ON user_language_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Функция для получения перевода знания
CREATE OR REPLACE FUNCTION get_knowledge_translation(
    node_id UUID,
    lang_code VARCHAR(10) DEFAULT 'en'
)
RETURNS TEXT AS $$
DECLARE
    translated TEXT;
    original_content TEXT;
BEGIN
    -- Пытаемся получить перевод
    SELECT translated_content INTO translated
    FROM knowledge_translations
    WHERE knowledge_node_id = node_id
      AND language_code = lang_code;
    
    -- Если перевода нет, возвращаем оригинал
    IF translated IS NULL THEN
        SELECT content INTO original_content
        FROM knowledge_nodes
        WHERE id = node_id;
        RETURN original_content;
    END IF;
    
    RETURN translated;
END;
$$ LANGUAGE plpgsql;

-- Функция для мультиязычного поиска
CREATE OR REPLACE FUNCTION search_knowledge_multilang(
    search_query TEXT,
    lang_code VARCHAR(10) DEFAULT 'auto',
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    node_id UUID,
    content TEXT,
    language_code VARCHAR(10),
    confidence_score FLOAT,
    domain_name VARCHAR
) AS $$
BEGIN
    -- Если auto, пытаемся определить язык
    IF lang_code = 'auto' THEN
        -- Простая эвристика (можно улучшить)
        IF search_query ~ '[а-яА-Я]' THEN
            lang_code := 'ru';
        ELSE
            lang_code := 'en';
        END IF;
    END IF;
    
    RETURN QUERY
    SELECT 
        k.id as node_id,
        COALESCE(kt.translated_content, k.content) as content,
        COALESCE(kt.language_code, 'original') as language_code,
        k.confidence_score,
        d.name as domain_name
    FROM knowledge_nodes k
    JOIN domains d ON k.domain_id = d.id
    LEFT JOIN knowledge_translations kt ON k.id = kt.knowledge_node_id 
        AND kt.language_code = lang_code
    WHERE 
        k.content ILIKE '%' || search_query || '%'
        OR kt.translated_content ILIKE '%' || search_query || '%'
    ORDER BY k.confidence_score DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Комментарии
COMMENT ON TABLE knowledge_translations IS 'Переводы знаний на разные языки';
COMMENT ON TABLE ui_translations IS 'Локализация интерфейса';
COMMENT ON TABLE user_language_preferences IS 'Языковые настройки пользователей';
COMMENT ON FUNCTION get_knowledge_translation IS 'Получение перевода знания на указанный язык';
COMMENT ON FUNCTION search_knowledge_multilang IS 'Мультиязычный поиск знаний';

