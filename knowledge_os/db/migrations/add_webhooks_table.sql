-- Migration: Add webhooks table for external integrations
-- Дата: 2025-12-14
-- Версия: Singularity 4.0

-- Таблица для webhooks
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_type VARCHAR(50) NOT NULL, -- 'slack', 'discord', 'telegram', 'custom'
    url TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    events JSONB DEFAULT '[]', -- Список событий для подписки (пустой = все события)
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_webhooks_type ON webhooks (webhook_type);
CREATE INDEX IF NOT EXISTS idx_webhooks_enabled ON webhooks (enabled);
CREATE INDEX IF NOT EXISTS idx_webhooks_events ON webhooks USING GIN (events);

-- Таблица для логов webhooks
CREATE TABLE IF NOT EXISTS webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    success BOOLEAN DEFAULT FALSE,
    response JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для логов
CREATE INDEX IF NOT EXISTS idx_webhook_logs_webhook ON webhook_logs (webhook_id);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_event ON webhook_logs (event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_success ON webhook_logs (success);
CREATE INDEX IF NOT EXISTS idx_webhook_logs_created ON webhook_logs (created_at DESC);

-- Триггер для updated_at
DROP TRIGGER IF EXISTS update_webhooks_updated_at ON webhooks;
CREATE TRIGGER update_webhooks_updated_at
    BEFORE UPDATE ON webhooks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Комментарии
COMMENT ON TABLE webhooks IS 'Webhooks для интеграции с внешними системами (Slack, Discord, Telegram, Custom)';
COMMENT ON TABLE webhook_logs IS 'Логи отправки webhooks для отладки и мониторинга';

