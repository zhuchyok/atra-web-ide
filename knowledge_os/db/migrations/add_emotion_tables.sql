-- Migration: Add Emotion tables (Singularity 9.0)
-- Purpose: Store emotion detection data for Emotional Response Modulation
-- Date: 2026-01-16

CREATE TABLE IF NOT EXISTS emotion_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_log_id UUID,  -- Связь с interaction_logs (без FK из-за возможного несоответствия типов)
    detected_emotion VARCHAR(50),  -- frustrated, rushed, curious, calm
    emotion_confidence FLOAT DEFAULT 0.0,      -- 0.0-1.0
    tone_used VARCHAR(100),        -- calm_supportive, concise_direct, etc.
    detail_level VARCHAR(50),      -- high, medium, very_high, normal
    feedback_score INTEGER,        -- Связь с feedback_score из interaction_logs
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emotion_logs_interaction ON emotion_logs(interaction_log_id);
CREATE INDEX IF NOT EXISTS idx_emotion_logs_emotion ON emotion_logs(detected_emotion);
CREATE INDEX IF NOT EXISTS idx_emotion_logs_feedback ON emotion_logs(feedback_score);

COMMENT ON TABLE emotion_logs IS 'Логи детекции эмоций для Emotional Response Modulation (Singularity 9.0)';
COMMENT ON COLUMN emotion_logs.detected_emotion IS 'Детектированная эмоция: frustrated, rushed, curious, calm';
COMMENT ON COLUMN emotion_logs.emotion_confidence IS 'Уверенность в детекции эмоции (0.0-1.0)';
COMMENT ON COLUMN emotion_logs.tone_used IS 'Использованный тон ответа на основе эмоции';
COMMENT ON COLUMN emotion_logs.detail_level IS 'Уровень детализации ответа на основе эмоции';

