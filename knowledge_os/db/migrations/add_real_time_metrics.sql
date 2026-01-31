-- Миграция для добавления таблицы real_time_metrics
-- Singularity 7.5: Observability and Autonomous Operations

CREATE TABLE IF NOT EXISTS real_time_metrics (
    id SERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC NOT NULL,
    metric_unit TEXT, -- 'tokens_per_second', 'cost_per_response', 'cpu_temp', 'gpu_temp', 'compression_ratio'
    source TEXT, -- 'local_mac', 'local_server', 'cloud', 'system'
    metadata JSONB, -- Дополнительные данные метрики
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rt_metrics_name ON real_time_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_rt_metrics_created_at ON real_time_metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_rt_metrics_source ON real_time_metrics(source);
CREATE INDEX IF NOT EXISTS idx_rt_metrics_name_time ON real_time_metrics(metric_name, created_at DESC);

-- Индекс для быстрого получения последних метрик
-- Используем частичный индекс без WHERE для совместимости
CREATE INDEX IF NOT EXISTS idx_rt_metrics_recent ON real_time_metrics(created_at DESC);

COMMENT ON TABLE real_time_metrics IS 'Хранилище реальных метрик производительности системы для анализа трендов';
COMMENT ON COLUMN real_time_metrics.metric_name IS 'Название метрики (tokens_per_second, cost_per_response, cpu_temp, gpu_temp, compression_ratio)';
COMMENT ON COLUMN real_time_metrics.metric_value IS 'Значение метрики';
COMMENT ON COLUMN real_time_metrics.metric_unit IS 'Единица измерения метрики';
COMMENT ON COLUMN real_time_metrics.source IS 'Источник метрики (local_mac, local_server, cloud, system)';
COMMENT ON COLUMN real_time_metrics.metadata IS 'Дополнительные данные метрики в формате JSON';

