-- Метрики производительности моделей: время загрузки, выгрузки, развёртывания, обработки.
-- Заполняется при появлении новой модели (probe) и используется с запасом для таймаутов и выбора модели.

CREATE TABLE IF NOT EXISTS model_performance_metrics (
    id SERIAL PRIMARY KEY,
    model_name TEXT NOT NULL,
    source TEXT NOT NULL,  -- 'ollama' | 'mlx'
    base_url TEXT,
    -- Измеренные значения (секунды)
    load_time_sec NUMERIC,
    unload_time_sec NUMERIC,
    deploy_time_sec NUMERIC,  -- время до готовности (часто = load_time_sec)
    processing_sec_per_1k_tokens NUMERIC,  -- среднее время на 1k токенов инференса
    -- С запасом (для таймаутов и планирования): измеренное * margin
    load_time_sec_with_margin NUMERIC,
    unload_time_sec_with_margin NUMERIC,
    deploy_time_sec_with_margin NUMERIC,
    processing_sec_per_1k_with_margin NUMERIC,
    margin_factor NUMERIC DEFAULT 1.2,  -- коэффициент запаса (например 1.2 = +20%)
    probe_count INTEGER DEFAULT 0,
    last_probed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_name, source)
);

CREATE INDEX IF NOT EXISTS idx_model_perf_name ON model_performance_metrics(model_name);
CREATE INDEX IF NOT EXISTS idx_model_perf_source ON model_performance_metrics(source);
CREATE INDEX IF NOT EXISTS idx_model_perf_last_probed ON model_performance_metrics(last_probed_at);

COMMENT ON TABLE model_performance_metrics IS 'Время загрузки/выгрузки/развёртывания/обработки по моделям; заполняется probe при появлении новой модели; используется с запасом';
COMMENT ON COLUMN model_performance_metrics.load_time_sec IS 'Измеренное время загрузки модели (сек)';
COMMENT ON COLUMN model_performance_metrics.unload_time_sec IS 'Измеренное время выгрузки модели (сек)';
COMMENT ON COLUMN model_performance_metrics.deploy_time_sec IS 'Время развёртывания до готовности (сек)';
COMMENT ON COLUMN model_performance_metrics.processing_sec_per_1k_tokens IS 'Среднее время инференса на 1k токенов (сек)';
COMMENT ON COLUMN model_performance_metrics.load_time_sec_with_margin IS 'load_time_sec * margin_factor для таймаутов';
COMMENT ON COLUMN model_performance_metrics.margin_factor IS 'Коэффициент запаса (напр. 1.2 = +20%)';
