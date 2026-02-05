-- Миграция: таблица board_decisions для аудита решений Совета Директоров
-- Дата: 2026-01-27
-- Цель: структурированное хранение решений Совета с полным аудитом

-- Создание таблицы board_decisions
CREATE TABLE IF NOT EXISTS board_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Источник запроса
    source TEXT NOT NULL CHECK (source IN ('chat', 'api', 'nightly', 'dashboard')),
    
    -- Идентификаторы для трассировки
    correlation_id TEXT,  -- Связь с запросом чата/задачи
    session_id TEXT,      -- ID сессии (для чата)
    user_id TEXT,         -- ID пользователя (для чата)
    
    -- Вопрос и контекст
    question TEXT NOT NULL,
    context_snapshot JSONB,  -- Краткий контекст (OKR, метрики) на момент решения
    
    -- Решение Совета
    directive_text TEXT NOT NULL,  -- Полный текст решения/директивы
    structured_decision JSONB,     -- Структурированное решение (decision, rationale, risks, confidence)
    
    -- Оценка риска
    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high')),
    recommend_human_review BOOLEAN DEFAULT FALSE
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_board_decisions_created_at 
    ON board_decisions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_board_decisions_source 
    ON board_decisions (source);

CREATE INDEX IF NOT EXISTS idx_board_decisions_correlation_id 
    ON board_decisions (correlation_id) 
    WHERE correlation_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_board_decisions_risk_level 
    ON board_decisions (risk_level) 
    WHERE risk_level IS NOT NULL;

-- GIN индекс для поиска по structured_decision
CREATE INDEX IF NOT EXISTS idx_board_decisions_structured 
    ON board_decisions USING GIN (structured_decision);

-- Комментарии для документации
COMMENT ON TABLE board_decisions IS 'Аудит решений Совета Директоров с полной трассируемостью';
COMMENT ON COLUMN board_decisions.source IS 'Источник запроса: chat (из чата), api (прямой вызов), nightly (ежедневное заседание), dashboard (из дашборда)';
COMMENT ON COLUMN board_decisions.correlation_id IS 'ID для связи с запросом в чате или задачей';
COMMENT ON COLUMN board_decisions.context_snapshot IS 'Контекст на момент решения: OKR, метрики задач, последние знания';
COMMENT ON COLUMN board_decisions.structured_decision IS 'Структура: {decision: str, rationale: str, action_items: [{owner, task, deadline}], risks: [{risk, mitigation}], confidence: 0-1}';
COMMENT ON COLUMN board_decisions.risk_level IS 'Уровень риска решения: low, medium, high';
COMMENT ON COLUMN board_decisions.recommend_human_review IS 'Флаг: требуется подтверждение человеком при высоком риске или низкой уверенности';
