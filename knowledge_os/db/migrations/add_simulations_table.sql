-- Таблица симуляций для дашборда (Инструменты экспертов → Симулятор).
-- Используется: scout_tab.py (INSERT/SELECT), simulator.py (SELECT idea, UPDATE result).
-- Применение: psql $DATABASE_URL -f knowledge_os/db/migrations/add_simulations_table.sql

CREATE TABLE IF NOT EXISTS simulations (
    id SERIAL PRIMARY KEY,
    idea TEXT NOT NULL,
    result TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON simulations(created_at DESC);
COMMENT ON TABLE simulations IS 'Симуляции бизнес-идей (дашборд + simulator.py)';
