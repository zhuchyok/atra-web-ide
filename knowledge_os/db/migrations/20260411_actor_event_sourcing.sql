-- [SINGULARITY 26.3] Event Sourcing for AI Actors
-- Таблица для хранения снимков состояний акторов
CREATE TABLE IF NOT EXISTS actor_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_name VARCHAR(255) NOT NULL,
    task_id UUID,
    state_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Таблица для лога событий (дельты изменений)
CREATE TABLE IF NOT EXISTS actor_events (
    id BIGSERIAL PRIMARY KEY,
    actor_name VARCHAR(255) NOT NULL,
    task_id UUID,
    event_type VARCHAR(100) NOT NULL, -- e.g., 'thought', 'handoff_initiated', 'reply_generated'
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого восстановления
CREATE INDEX IF NOT EXISTS idx_actor_states_actor_task ON actor_states(actor_name, task_id);
CREATE INDEX IF NOT EXISTS idx_actor_events_actor_task ON actor_events(actor_name, task_id);
