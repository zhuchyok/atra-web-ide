-- Миграция для threat detection

CREATE TABLE IF NOT EXISTS threat_detection_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    threat_type TEXT NOT NULL, -- 'data_leak', 'prompt_injection', 'model_poisoning', 'resource_exhaustion'
    severity TEXT NOT NULL, -- 'low', 'medium', 'high', 'critical'
    detected_in TEXT, -- 'query', 'response', 'feedback'
    details JSONB,
    action_taken TEXT,
    resolved BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_threat_detection_timestamp ON threat_detection_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_threat_detection_type ON threat_detection_logs(threat_type);
CREATE INDEX IF NOT EXISTS idx_threat_detection_severity ON threat_detection_logs(severity);
CREATE INDEX IF NOT EXISTS idx_threat_detection_resolved ON threat_detection_logs(resolved);

COMMENT ON TABLE threat_detection_logs IS 'Логи детектирования угроз безопасности';
COMMENT ON COLUMN threat_detection_logs.threat_type IS 'Тип угрозы';
COMMENT ON COLUMN threat_detection_logs.severity IS 'Уровень серьезности угрозы';

