-- Миграция для добавления таблицы логирования аномалий
-- Singularity 7.5: Observability and Autonomous Operations

CREATE TABLE IF NOT EXISTS anomaly_detection_logs (
    id SERIAL PRIMARY KEY,
    anomaly_type TEXT NOT NULL, -- 'ddos', 'brute_force', 'injection', 'rate_spike', 'resource_attack'
    severity TEXT NOT NULL, -- 'high', 'medium', 'low'
    description TEXT NOT NULL,
    metadata JSONB, -- Дополнительные данные аномалии
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_anomaly_type ON anomaly_detection_logs(anomaly_type);
CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON anomaly_detection_logs(severity);
CREATE INDEX IF NOT EXISTS idx_anomaly_detected_at ON anomaly_detection_logs(detected_at);
-- Индекс для быстрого доступа к недавним аномалиям (без WHERE для совместимости)
CREATE INDEX IF NOT EXISTS idx_anomaly_recent ON anomaly_detection_logs(detected_at DESC);

COMMENT ON TABLE anomaly_detection_logs IS 'Логи обнаруженных аномалий в запросах (DDoS, brute force, инъекции)';
COMMENT ON COLUMN anomaly_detection_logs.anomaly_type IS 'Тип аномалии (ddos, brute_force, injection, rate_spike, resource_attack)';
COMMENT ON COLUMN anomaly_detection_logs.severity IS 'Серьезность аномалии (high, medium, low)';
COMMENT ON COLUMN anomaly_detection_logs.description IS 'Описание аномалии';
COMMENT ON COLUMN anomaly_detection_logs.metadata IS 'Дополнительные данные аномалии в формате JSON';

