-- Триггер для автоматической синхронизации employees.json при изменениях в experts
-- Отправляет NOTIFY 'experts_changed' при INSERT/UPDATE/DELETE

-- Функция триггера
CREATE OR REPLACE FUNCTION notify_experts_changed()
RETURNS TRIGGER AS $$
DECLARE
    payload JSON;
BEGIN
    IF TG_OP = 'DELETE' THEN
        payload := json_build_object(
            'operation', TG_OP,
            'expert_id', OLD.id,
            'name', OLD.name,
            'timestamp', NOW()
        );
    ELSE
        payload := json_build_object(
            'operation', TG_OP,
            'expert_id', NEW.id,
            'name', NEW.name,
            'role', NEW.role,
            'department', NEW.department,
            'timestamp', NOW()
        );
    END IF;
    
    PERFORM pg_notify('experts_changed', payload::text);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Триггер на таблицу experts
DROP TRIGGER IF EXISTS experts_sync_trigger ON experts;
CREATE TRIGGER experts_sync_trigger
    AFTER INSERT OR UPDATE OR DELETE ON experts
    FOR EACH ROW
    EXECUTE FUNCTION notify_experts_changed();

-- Комментарий
COMMENT ON FUNCTION notify_experts_changed() IS 
'Отправляет pg_notify при изменениях в experts для автосинхронизации employees.json';
