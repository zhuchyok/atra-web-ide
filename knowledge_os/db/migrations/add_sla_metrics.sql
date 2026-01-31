-- Миграция для SLA метрик

CREATE TABLE IF NOT EXISTS sla_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metric_name TEXT NOT NULL,
    metric_value FLOAT NOT NULL,
    target_value FLOAT NOT NULL,
    compliant BOOLEAN NOT NULL,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_sla_metrics_timestamp ON sla_metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_sla_metrics_name ON sla_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_sla_metrics_compliant ON sla_metrics(compliant);

COMMENT ON TABLE sla_metrics IS 'Метрики SLA для мониторинга соответствия Service Level Agreements';
COMMENT ON COLUMN sla_metrics.metric_name IS 'Название метрики (p95_latency, availability, cache_hit_rate)';
COMMENT ON COLUMN sla_metrics.compliant IS 'Соответствует ли метрика SLA';

