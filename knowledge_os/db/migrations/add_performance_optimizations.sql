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

-- Партиции для knowledge_nodes только если таблица уже партиционирована (relkind = 'p')
DO $$
DECLARE
    start_date DATE := '2024-01-01';
    end_date DATE := '2026-12-31';
    cur_date DATE;
    partition_name TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'knowledge_nodes' AND relkind = 'p') THEN
        cur_date := start_date;
        WHILE cur_date <= end_date LOOP
            partition_name := 'knowledge_nodes_' || to_char(cur_date, 'YYYY_MM');
            EXECUTE format('
                CREATE TABLE IF NOT EXISTS %I PARTITION OF knowledge_nodes
                FOR VALUES FROM (%L) TO (%L)
            ', partition_name, cur_date, cur_date + INTERVAL '1 month');
            cur_date := cur_date + INTERVAL '1 month';
        END LOOP;
    END IF;
END $$;

-- Партиции для tasks только если таблица уже партиционирована
DO $$
DECLARE
    start_date DATE := '2024-01-01';
    end_date DATE := '2026-12-31';
    cur_date DATE;
    partition_name TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'tasks' AND relkind = 'p') THEN
        cur_date := start_date;
        WHILE cur_date <= end_date LOOP
            partition_name := 'tasks_' || to_char(cur_date, 'YYYY_MM');
            EXECUTE format('
                CREATE TABLE IF NOT EXISTS %I PARTITION OF tasks
                FOR VALUES FROM (%L) TO (%L)
            ', partition_name, cur_date, cur_date + INTERVAL '1 month');
            cur_date := cur_date + INTERVAL '1 month';
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

