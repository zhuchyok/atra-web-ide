-- Миграция для добавления таблицы логирования Circuit Breaker
-- Singularity 7.5: Observability and Autonomous Operations

CREATE TABLE IF NOT EXISTS circuit_breaker_events (
    id SERIAL PRIMARY KEY,
    breaker_name TEXT NOT NULL,
    event_type TEXT NOT NULL, -- 'state_change', 'failure', 'success', 'recovery_attempt'
    old_state TEXT, -- Предыдущее состояние
    new_state TEXT, -- Новое состояние
    failure_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_message TEXT,
    metadata JSONB, -- Дополнительные данные события
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cb_events_breaker_name ON circuit_breaker_events(breaker_name);
CREATE INDEX IF NOT EXISTS idx_cb_events_event_type ON circuit_breaker_events(event_type);
CREATE INDEX IF NOT EXISTS idx_cb_events_created_at ON circuit_breaker_events(created_at);
CREATE INDEX IF NOT EXISTS idx_cb_events_new_state ON circuit_breaker_events(new_state);

-- Индекс для быстрого поиска открытых circuit breakers
CREATE INDEX IF NOT EXISTS idx_cb_events_open_state ON circuit_breaker_events(new_state) WHERE new_state = 'open';

COMMENT ON TABLE circuit_breaker_events IS 'Логи всех событий Circuit Breaker для анализа и мониторинга';
COMMENT ON COLUMN circuit_breaker_events.breaker_name IS 'Имя circuit breaker (например, database, local_models, cloud)';
COMMENT ON COLUMN circuit_breaker_events.event_type IS 'Тип события: state_change, failure, success, recovery_attempt';
COMMENT ON COLUMN circuit_breaker_events.old_state IS 'Предыдущее состояние (closed, open, half_open)';
COMMENT ON COLUMN circuit_breaker_events.new_state IS 'Новое состояние (closed, open, half_open)';
COMMENT ON COLUMN circuit_breaker_events.metadata IS 'Дополнительные данные события в формате JSON';

