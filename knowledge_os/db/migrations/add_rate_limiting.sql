-- Миграция для создания таблицы rate limiting
-- Singularity 8.0: Security and Reliability

CREATE TABLE IF NOT EXISTS rate_limits (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    request_count INTEGER DEFAULT 1,
    blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_rate_limits_user_id ON rate_limits(user_id);
CREATE INDEX IF NOT EXISTS idx_rate_limits_created_at ON rate_limits(created_at);
CREATE INDEX IF NOT EXISTS idx_rate_limits_blocked ON rate_limits(blocked) WHERE blocked = TRUE;

-- Комментарии
COMMENT ON TABLE rate_limits IS 'Rate limiting для защиты от злоупотреблений';
COMMENT ON COLUMN rate_limits.user_id IS 'ID пользователя или идентификатор';
COMMENT ON COLUMN rate_limits.blocked IS 'Заблокирован ли пользователь';

