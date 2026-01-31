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
    interaction_log_id UUID REFERENCES interaction_logs(id),
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

-- Триггеры для updated_at
CREATE TRIGGER update_contextual_patterns_updated_at
    BEFORE UPDATE ON contextual_patterns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

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

-- Migration: Performance optimizations (indexes, partitioning, caching)
-- Дата: 2025-12-14
-- Версия: Singularity 4.2

-- ============================================
-- ДОПОЛНИТЕЛЬНЫЕ ИНДЕКСЫ ДЛЯ ЧАСТЫХ ЗАПРОСОВ
-- ============================================

-- Индексы для knowledge_nodes
CREATE INDEX IF NOT EXISTS idx_knowledge_confidence ON knowledge_nodes (confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge_nodes (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_updated ON knowledge_nodes (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_verified ON knowledge_nodes (is_verified) WHERE is_verified = TRUE;

-- Композитный индекс для частого запроса: поиск по домену и confidence
CREATE INDEX IF NOT EXISTS idx_knowledge_domain_confidence 
    ON knowledge_nodes (domain_id, confidence_score DESC);

-- Индексы для tasks
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks (assignee_expert_id);
CREATE INDEX IF NOT EXISTS idx_tasks_creator ON tasks (creator_expert_id);
CREATE INDEX IF NOT EXISTS idx_tasks_domain ON tasks (domain_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks (completed_at DESC) WHERE completed_at IS NOT NULL;

-- Композитный индекс для частого запроса: задачи по статусу и приоритету
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority 
    ON tasks (status, priority DESC, created_at ASC);

-- Индексы для interaction_logs
CREATE INDEX IF NOT EXISTS idx_interaction_expert ON interaction_logs (expert_id);
CREATE INDEX IF NOT EXISTS idx_interaction_created ON interaction_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interaction_feedback ON interaction_logs (feedback_score) WHERE feedback_score IS NOT NULL;

-- Композитный индекс для частого запроса: логи по эксперту и дате
CREATE INDEX IF NOT EXISTS idx_interaction_expert_created 
    ON interaction_logs (expert_id, created_at DESC);

-- Индексы для experts
CREATE INDEX IF NOT EXISTS idx_experts_department ON experts (department);
CREATE INDEX IF NOT EXISTS idx_experts_role ON experts (role);
CREATE INDEX IF NOT EXISTS idx_experts_active ON experts (is_active) WHERE is_active = TRUE;

-- ============================================
-- ПАРТИЦИОНИРОВАНИЕ ТАБЛИЦ
-- ============================================

-- Партиционирование knowledge_nodes по дате создания (если еще не сделано)
-- Создаем партиции для каждого месяца
DO $$
DECLARE
    start_date DATE := '2024-01-01';
    end_date DATE := '2026-12-31';
    current_date DATE;
    partition_name TEXT;
BEGIN
    -- Проверяем, не партиционирована ли уже таблица
    IF NOT EXISTS (
        SELECT 1 FROM pg_class WHERE relname = 'knowledge_nodes' AND relkind = 'p'
    ) THEN
        -- Создаем партиции по месяцам
        current_date := start_date;
        WHILE current_date <= end_date LOOP
            partition_name := 'knowledge_nodes_' || to_char(current_date, 'YYYY_MM');
            
            EXECUTE format('
                CREATE TABLE IF NOT EXISTS %I PARTITION OF knowledge_nodes
                FOR VALUES FROM (%L) TO (%L)
            ', partition_name, current_date, current_date + INTERVAL '1 month');
            
            current_date := current_date + INTERVAL '1 month';
        END LOOP;
    END IF;
END $$;

-- Партиционирование tasks по дате создания
DO $$
DECLARE
    start_date DATE := '2024-01-01';
    end_date DATE := '2026-12-31';
    current_date DATE;
    partition_name TEXT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_class WHERE relname = 'tasks' AND relkind = 'p'
    ) THEN
        current_date := start_date;
        WHILE current_date <= end_date LOOP
            partition_name := 'tasks_' || to_char(current_date, 'YYYY_MM');
            
            EXECUTE format('
                CREATE TABLE IF NOT EXISTS %I PARTITION OF tasks
                FOR VALUES FROM (%L) TO (%L)
            ', partition_name, current_date, current_date + INTERVAL '1 month');
            
            current_date := current_date + INTERVAL '1 month';
        END LOOP;
    END IF;
END $$;

-- ============================================
-- МАТЕРИАЛИЗОВАННЫЕ ПРЕДСТАВЛЕНИЯ ДЛЯ КЭШИРОВАНИЯ
-- ============================================

-- Материализованное представление для статистики по доменам
CREATE MATERIALIZED VIEW IF NOT EXISTS domain_stats_cache AS
SELECT 
    d.id as domain_id,
    d.name as domain_name,
    count(k.id) as knowledge_count,
    avg(k.confidence_score) as avg_confidence,
    sum(COALESCE((k.metadata->>'usage_count')::int, 0)) as total_usage,
    max(k.created_at) as last_knowledge_created
FROM domains d
LEFT JOIN knowledge_nodes k ON d.id = k.domain_id
GROUP BY d.id, d.name;

-- Индекс для быстрого поиска
CREATE UNIQUE INDEX IF NOT EXISTS idx_domain_stats_domain ON domain_stats_cache (domain_id);

-- Материализованное представление для статистики экспертов
CREATE MATERIALIZED VIEW IF NOT EXISTS expert_stats_cache AS
SELECT 
    e.id as expert_id,
    e.name as expert_name,
    e.role,
    count(DISTINCT k.id) as knowledge_created,
    avg(k.confidence_score) as avg_knowledge_confidence,
    count(DISTINCT t.id) as tasks_completed,
    avg(il.feedback_score) as avg_feedback
FROM experts e
LEFT JOIN knowledge_nodes k ON k.metadata->>'expert' = e.name
LEFT JOIN tasks t ON t.assignee_expert_id = e.id AND t.status = 'completed'
LEFT JOIN interaction_logs il ON il.expert_id = e.id AND il.feedback_score IS NOT NULL
GROUP BY e.id, e.name, e.role;

-- Индекс для быстрого поиска
CREATE UNIQUE INDEX IF NOT EXISTS idx_expert_stats_expert ON expert_stats_cache (expert_id);

-- Функция для обновления кэша
CREATE OR REPLACE FUNCTION refresh_performance_cache()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY domain_stats_cache;
    REFRESH MATERIALIZED VIEW CONCURRENTLY expert_stats_cache;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- ОПТИМИЗАЦИЯ ЗАПРОСОВ
-- ============================================

-- Функция для анализа и оптимизации медленных запросов
CREATE OR REPLACE FUNCTION analyze_slow_queries()
RETURNS TABLE (
    query_text TEXT,
    calls BIGINT,
    total_time DOUBLE PRECISION,
    mean_time DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        query,
        calls,
        total_exec_time,
        mean_exec_time
    FROM pg_stat_statements
    WHERE mean_exec_time > 100  -- Запросы медленнее 100ms
    ORDER BY mean_exec_time DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- НАСТРОЙКИ ПРОИЗВОДИТЕЛЬНОСТИ
-- ============================================

-- Увеличиваем shared_buffers (требует перезапуска PostgreSQL)
-- ALTER SYSTEM SET shared_buffers = '256MB';

-- Увеличиваем work_mem для сложных запросов
-- ALTER SYSTEM SET work_mem = '16MB';

-- Включаем pg_stat_statements для мониторинга
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Комментарии
COMMENT ON MATERIALIZED VIEW domain_stats_cache IS 'Кэш статистики по доменам для быстрого доступа';
COMMENT ON MATERIALIZED VIEW expert_stats_cache IS 'Кэш статистики по экспертам для быстрого доступа';
COMMENT ON FUNCTION refresh_performance_cache IS 'Обновление материализованных представлений (кэша)';
COMMENT ON FUNCTION analyze_slow_queries IS 'Анализ медленных запросов для оптимизации';

-- Migration: Add security tables (users, audit_logs)
-- Дата: 2025-12-14
-- Версия: Singularity 4.1

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user', -- 'admin', 'user', 'readonly', 'api'
    email TEXT, -- Зашифрованное
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
CREATE INDEX IF NOT EXISTS idx_users_active ON users (is_active);

-- Таблица для аудита действий
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL, -- 'authentication', 'create_knowledge', 'delete_knowledge', etc.
    status VARCHAR(50) NOT NULL, -- 'success', 'failure', 'error'
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для аудита
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_status ON audit_logs (status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_details ON audit_logs USING GIN (details);

-- Таблица для JWT токенов (опционально, для отзыва токенов)
CREATE TABLE IF NOT EXISTS revoked_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    revoked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reason TEXT
);

-- Индекс для отозванных токенов
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_hash ON revoked_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user ON revoked_tokens (user_id);

-- Триггеры
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Функция для очистки старых логов аудита (старше 90 дней)
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs()
RETURNS void AS $$
BEGIN
    DELETE FROM audit_logs
    WHERE created_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

-- Комментарии
COMMENT ON TABLE users IS 'Пользователи системы с ролями и правами доступа';
COMMENT ON TABLE audit_logs IS 'Логи аудита всех действий пользователей';
COMMENT ON TABLE revoked_tokens IS 'Отозванные JWT токены';

-- Migration to add semantic AI cache
CREATE TABLE IF NOT EXISTS semantic_ai_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    embedding vector(768),
    expert_name VARCHAR(255),
    usage_count INTEGER DEFAULT 1,
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(query_text, expert_name)
);

CREATE INDEX IF NOT EXISTS idx_semantic_cache_embedding ON semantic_ai_cache USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_semantic_cache_expert ON semantic_ai_cache (expert_name);

-- Migration: Add tasks table with priority support
-- Date: 2025-12-14
-- Version: Singularity 3.1

-- Tasks table with priority and workload balancing
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- pending, in_progress, completed, failed, cancelled
    priority VARCHAR(20) DEFAULT 'medium', -- urgent, high, medium, low
    assignee_expert_id UUID REFERENCES experts(id),
    creator_expert_id UUID REFERENCES experts(id),
    domain_id UUID REFERENCES domains(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_duration_minutes INTEGER, -- Estimated time to complete
    actual_duration_minutes INTEGER -- Actual time taken
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks (assignee_expert_id);
CREATE INDEX IF NOT EXISTS idx_tasks_creator ON tasks (creator_expert_id);
CREATE INDEX IF NOT EXISTS idx_tasks_domain ON tasks (domain_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks (created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_metadata ON tasks USING GIN (metadata);

-- Composite index for task selection queries
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority ON tasks (status, priority, created_at);

-- Trigger for updated_at
CREATE TRIGGER update_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add usage_count to knowledge_nodes if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'knowledge_nodes' AND column_name = 'usage_count'
    ) THEN
        ALTER TABLE knowledge_nodes ADD COLUMN usage_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- Add is_verified to knowledge_nodes if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'knowledge_nodes' AND column_name = 'is_verified'
    ) THEN
        ALTER TABLE knowledge_nodes ADD COLUMN is_verified BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- Add department to experts if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'experts' AND column_name = 'department'
    ) THEN
        ALTER TABLE experts ADD COLUMN department VARCHAR(255);
    END IF;
END $$;

-- Add last_learned_at to experts if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'experts' AND column_name = 'last_learned_at'
    ) THEN
        ALTER TABLE experts ADD COLUMN last_learned_at TIMESTAMP WITH TIME ZONE;
    END IF;
END $$;

-- Add version to experts if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'experts' AND column_name = 'version'
    ) THEN
        ALTER TABLE experts ADD COLUMN version INTEGER DEFAULT 1;
    END IF;
END $$;

-- Add notifications table if not exists
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message TEXT NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add expert_discussions table if not exists
CREATE TABLE IF NOT EXISTS expert_discussions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_node_id UUID REFERENCES knowledge_nodes(id),
    expert_ids UUID[],
    topic TEXT,
    consensus_summary TEXT,
    status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Add expert_learning_logs table (Nightly Learner, dashboard "Академия ИИ")
CREATE TABLE IF NOT EXISTS expert_learning_logs (
    id SERIAL PRIMARY KEY,
    expert_id UUID NOT NULL REFERENCES experts(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    summary TEXT,
    learned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_expert_learning_logs_expert_id ON expert_learning_logs (expert_id);
CREATE INDEX IF NOT EXISTS idx_expert_learning_logs_learned_at ON expert_learning_logs (learned_at DESC);

-- Add system_metrics table if not exists (for monitoring)
CREATE TABLE IF NOT EXISTS system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metrics JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics (timestamp);

-- Migration: Add webhooks table for external integrations
-- Дата: 2025-12-14
-- Версия: Singularity 4.0

-- Таблица для webhooks
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_type VARCHAR(50) NOT NULL, -- 'slack', 'discord', 'telegram', 'custom'
    url TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    events JSONB DEFAULT '[]', -- Список событий для подписки (пустой = все события)
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_webhooks_type ON webhooks (webhook_type);
CREATE INDEX IF NOT EXISTS idx_webhooks_enabled ON webhooks (enabled);
CREATE INDEX IF NOT EXISTS idx_webhooks_events ON webhooks USING GIN (events);

-- Таблица для логов webhooks
CREATE TABLE IF NOT EXISTS webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    success BOOLEAN DEFAULT FALSE,
    response JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для логов
CREATE INDEX IF NOT EXISTS idx_webhook_logs_webhook ON webhook_logs (webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_event ON webhook_logs (event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_success ON webhook_logs (success);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_created ON webhook_logs (created_at DESC);

-- Триггер для updated_at
CREATE TRIGGER update_webhooks_updated_at
    BEFORE UPDATE ON webhooks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Комментарии
COMMENT ON TABLE webhooks IS 'Webhooks для интеграции с внешними системами (Slack, Discord, Telegram, Custom)';
COMMENT ON TABLE webhook_logs IS 'Логи отправки webhooks для отладки и мониторинга';

