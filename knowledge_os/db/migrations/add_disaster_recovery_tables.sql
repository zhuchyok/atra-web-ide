-- Миграция для таблиц Disaster Recovery

-- Таблица для логирования изменений режимов работы системы
CREATE TABLE IF NOT EXISTS disaster_recovery_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    old_mode TEXT NOT NULL,
    new_mode TEXT NOT NULL,
    reason TEXT,
    component_states JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_disaster_recovery_logs_timestamp 
ON disaster_recovery_logs(timestamp);

CREATE INDEX IF NOT EXISTS idx_disaster_recovery_logs_mode 
ON disaster_recovery_logs(new_mode);

COMMENT ON TABLE disaster_recovery_logs IS 'Логи изменений режимов работы системы при аварийных ситуациях';
COMMENT ON COLUMN disaster_recovery_logs.old_mode IS 'Предыдущий режим работы';
COMMENT ON COLUMN disaster_recovery_logs.new_mode IS 'Новый режим работы';
COMMENT ON COLUMN disaster_recovery_logs.component_states IS 'Состояние компонентов системы на момент переключения';

