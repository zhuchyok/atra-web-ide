-- Миграция для исправления ошибок отсутствующих таблиц
-- 2026-02-13: Добавление таблиц для стратегий и дистилляции знаний

-- Таблица для сессий стратегического планирования
CREATE TABLE IF NOT EXISTS strategy_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active', -- active, completed, archived
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица для вопросов Discovery фазы
CREATE TABLE IF NOT EXISTS strategy_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES strategy_sessions(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    answer_text TEXT,
    is_answered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица для мастер-планов
CREATE TABLE IF NOT EXISTS master_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES strategy_sessions(id) ON DELETE CASCADE,
    goal TEXT NOT NULL,
    steps JSONB NOT NULL DEFAULT '[]',
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Таблица для синтетических данных (дистилляция знаний)
CREATE TABLE IF NOT EXISTS synthetic_training_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category TEXT NOT NULL,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    expert_id UUID REFERENCES experts(id),
    quality_score FLOAT DEFAULT 1.0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы для ускорения поиска
CREATE INDEX IF NOT EXISTS idx_strategy_sessions_status ON strategy_sessions(status);
CREATE INDEX IF NOT EXISTS idx_synthetic_data_category ON synthetic_training_data(category);
