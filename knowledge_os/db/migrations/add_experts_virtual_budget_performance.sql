-- Колонки для Финансов и ROI в дашборде (Стратегия → Финансы и ROI).
-- SUM(virtual_budget), AVG(performance_score) из experts — strategy_tab.py, charts.py.
-- Применение: psql $DATABASE_URL -f knowledge_os/db/migrations/add_experts_virtual_budget_performance.sql

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'experts' AND column_name = 'virtual_budget'
    ) THEN
        ALTER TABLE experts ADD COLUMN virtual_budget FLOAT DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'experts' AND column_name = 'performance_score'
    ) THEN
        ALTER TABLE experts ADD COLUMN performance_score FLOAT DEFAULT NULL;
    END IF;
END $$;

COMMENT ON COLUMN experts.virtual_budget IS 'Виртуальный бюджет эксперта (для дашборда Финансы и ROI)';
COMMENT ON COLUMN experts.performance_score IS 'Оценка производительности 0.0–1.0 (для дашборда и Consensus v2)';
