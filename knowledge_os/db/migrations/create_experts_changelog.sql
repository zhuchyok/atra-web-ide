"""
Database trigger для автоматической синхронизации при изменениях в таблице experts.

Создает webhook/задачу для обновления .cursor/rules/ при:
- INSERT (найм)
- UPDATE (изменение данных)
- DELETE (увольнение)
"""

-- Таблица для отслеживания изменений экспертов
CREATE TABLE IF NOT EXISTS experts_changelog (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(10) NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE'
    expert_id UUID,
    expert_name VARCHAR(255),
    expert_role VARCHAR(255),
    old_data JSONB,
    new_data JSONB,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    sync_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'completed', 'failed'
    sync_at TIMESTAMPTZ
);

-- Функция для логирования изменений
CREATE OR REPLACE FUNCTION log_expert_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO experts_changelog (event_type, expert_id, expert_name, expert_role, new_data)
        VALUES ('INSERT', NEW.id, NEW.name, NEW.role, row_to_json(NEW)::jsonb);
        
    ELSIF TG_OP = 'UPDATE' THEN
        -- Логируем только если изменились важные поля
        IF (OLD.name != NEW.name OR OLD.role != NEW.role OR OLD.department != NEW.department) THEN
            INSERT INTO experts_changelog (event_type, expert_id, expert_name, expert_role, old_data, new_data)
            VALUES ('UPDATE', NEW.id, NEW.name, NEW.role, row_to_json(OLD)::jsonb, row_to_json(NEW)::jsonb);
        END IF;
        
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO experts_changelog (event_type, expert_id, expert_name, expert_role, old_data)
        VALUES ('DELETE', OLD.id, OLD.name, OLD.role, row_to_json(OLD)::jsonb);
    END IF;
    
    -- Возвращаем NEW для INSERT/UPDATE, OLD для DELETE
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Триггер на таблицу experts
DROP TRIGGER IF EXISTS experts_changes_trigger ON experts;
CREATE TRIGGER experts_changes_trigger
    AFTER INSERT OR UPDATE OR DELETE ON experts
    FOR EACH ROW
    EXECUTE FUNCTION log_expert_changes();

-- Функция для получения pending изменений
CREATE OR REPLACE FUNCTION get_pending_expert_changes()
RETURNS TABLE (
    id INT,
    event_type VARCHAR,
    expert_name VARCHAR,
    expert_role VARCHAR,
    changed_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id,
        c.event_type,
        c.expert_name,
        c.expert_role,
        c.changed_at
    FROM experts_changelog c
    WHERE c.sync_status = 'pending'
    ORDER BY c.changed_at ASC;
END;
$$ LANGUAGE plpgsql;

-- Функция для отметки как синхронизированного
CREATE OR REPLACE FUNCTION mark_expert_change_synced(change_id INT)
RETURNS VOID AS $$
BEGIN
    UPDATE experts_changelog
    SET sync_status = 'completed',
        sync_at = NOW()
    WHERE id = change_id;
END;
$$ LANGUAGE plpgsql;

-- Представление для удобного просмотра изменений
CREATE OR REPLACE VIEW expert_changes_summary AS
SELECT 
    event_type,
    COUNT(*) as count,
    MAX(changed_at) as last_change
FROM experts_changelog
WHERE changed_at >= NOW() - INTERVAL '7 days'
GROUP BY event_type
ORDER BY event_type;

-- Комментарии
COMMENT ON TABLE experts_changelog IS 'Лог изменений экспертов для автосинхронизации .cursor/rules/';
COMMENT ON FUNCTION log_expert_changes() IS 'Логирует изменения в таблице experts';
COMMENT ON FUNCTION get_pending_expert_changes() IS 'Получить несинхронизированные изменения';
COMMENT ON FUNCTION mark_expert_change_synced(INT) IS 'Отметить изменение как синхронизированное';
