-- Migration: Add expert_learning_logs table for Nightly Learner
-- Used by: nightly_learner.py (INSERT), dashboard (SELECT for "Академия ИИ")
-- Date: 2026-01-29

CREATE TABLE IF NOT EXISTS expert_learning_logs (
    id SERIAL PRIMARY KEY,
    expert_id UUID NOT NULL REFERENCES experts(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    summary TEXT,
    learned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_expert_learning_logs_expert_id ON expert_learning_logs (expert_id);
CREATE INDEX IF NOT EXISTS idx_expert_learning_logs_learned_at ON expert_learning_logs (learned_at DESC);

COMMENT ON TABLE expert_learning_logs IS 'Логи обучения экспертов (Nightly Learner), отображаются в дашборде Академия ИИ';
