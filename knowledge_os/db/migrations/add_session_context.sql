-- Миграция для создания таблицы контекста сессий
-- Singularity 8.0: Intelligent Improvements

CREATE TABLE IF NOT EXISTS session_context (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    expert_name TEXT NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_session_context_session_id ON session_context(session_id);
CREATE INDEX IF NOT EXISTS idx_session_context_created_at ON session_context(created_at);
CREATE INDEX IF NOT EXISTS idx_session_context_user_expert ON session_context(user_id, expert_name);

-- Комментарии
COMMENT ON TABLE session_context IS 'Контекст сессий пользователей для улучшения качества диалогов';
COMMENT ON COLUMN session_context.session_id IS 'Уникальный ID сессии (MD5 hash от user_id + expert_name)';
COMMENT ON COLUMN session_context.query_text IS 'Запрос пользователя (ограничено 500 символов)';
COMMENT ON COLUMN session_context.response_text IS 'Ответ системы (ограничено 2000 символов)';

