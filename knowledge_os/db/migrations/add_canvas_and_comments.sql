-- Миграция для системы интерактивных комментариев и паттернов (ATRA Canvas)
-- Дата: 2026-02-14

-- Таблица для хранения инлайн-комментариев экспертов к коду
CREATE TABLE IF NOT EXISTS file_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path TEXT NOT NULL,
    pattern TEXT, -- Regex или строка кода, к которой привязан комментарий
    line_number INTEGER, -- Опционально, если паттерн не используется
    comment_text TEXT NOT NULL,
    expert_id UUID REFERENCES experts(id),
    expert_name TEXT, -- Для быстрого отображения без JOIN
    status TEXT DEFAULT 'active', -- active, resolved, archived
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска по файлам
CREATE INDEX IF NOT EXISTS idx_file_comments_path ON file_comments(file_path);
CREATE INDEX IF NOT EXISTS idx_file_comments_status ON file_comments(status);

-- Таблица для отслеживания патчей и версий (Canvas Mode)
CREATE TABLE IF NOT EXISTS file_patches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path TEXT NOT NULL,
    pattern TEXT NOT NULL,
    replacement TEXT NOT NULL,
    expert_id UUID REFERENCES experts(id),
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_file_patches_path ON file_patches(file_path);
