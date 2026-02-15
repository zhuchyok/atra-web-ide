-- Долгосрочная память по пользователю/проекту (План «Логика мысли» Фаза 2).
-- Ключ: (user_key, project_context). user_key = session_id от клиента (пока отдельного user_id нет).
-- Используется для блока «Ранее по этому проекту/пользователю» в промпте Victoria.

CREATE TABLE IF NOT EXISTS long_term_memory (
    id SERIAL PRIMARY KEY,
    user_key TEXT NOT NULL,
    project_context TEXT NOT NULL,
    goal_summary TEXT NOT NULL,
    outcome_summary TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_long_term_memory_user_project ON long_term_memory(user_key, project_context);
CREATE INDEX IF NOT EXISTS idx_long_term_memory_created_at ON long_term_memory(created_at);

COMMENT ON TABLE long_term_memory IS 'Долгосрочная память: суммаризованные обмены по (user_key, project) для контекста Victoria';
COMMENT ON COLUMN long_term_memory.user_key IS 'Идентификатор пользователя/сессии (session_id от клиента)';
COMMENT ON COLUMN long_term_memory.project_context IS 'Контекст проекта (atra-web-ide, atra, …)';
COMMENT ON COLUMN long_term_memory.goal_summary IS 'Краткое описание запроса (до 500 символов)';
COMMENT ON COLUMN long_term_memory.outcome_summary IS 'Краткий итог ответа (до 500 символов)';
