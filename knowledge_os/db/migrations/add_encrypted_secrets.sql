-- Миграция для создания таблицы зашифрованных секретов
-- Singularity 8.0: Security and Reliability

CREATE TABLE IF NOT EXISTS encrypted_secrets (
    id SERIAL PRIMARY KEY,
    secret_name TEXT NOT NULL UNIQUE,
    encrypted_value TEXT NOT NULL,
    secret_type TEXT NOT NULL,  -- 'api_key', 'password', 'token', etc.
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,  -- Опциональная дата истечения
    rotation_days INTEGER DEFAULT 90  -- Интервал ротации в днях
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_encrypted_secrets_name ON encrypted_secrets(secret_name);
CREATE INDEX IF NOT EXISTS idx_encrypted_secrets_type ON encrypted_secrets(secret_type);
CREATE INDEX IF NOT EXISTS idx_encrypted_secrets_expires_at ON encrypted_secrets(expires_at) WHERE expires_at IS NOT NULL;

-- Комментарии
COMMENT ON TABLE encrypted_secrets IS 'Зашифрованные секреты (API ключи, пароли, токены)';
COMMENT ON COLUMN encrypted_secrets.encrypted_value IS 'Зашифрованное значение (base64)';
COMMENT ON COLUMN encrypted_secrets.rotation_days IS 'Интервал ротации ключа в днях (по умолчанию 90)';

