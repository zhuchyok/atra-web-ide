-- Миграция: Singularity 21.24 — Multi-Cluster Autonomy
-- Создание таблицы кластеров и модификация существующих таблиц

-- 1. Таблица кластеров
CREATE TABLE IF NOT EXISTS clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    status TEXT DEFAULT 'active', -- active, inactive, maintenance
    is_local BOOLEAN DEFAULT false,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для быстрого поиска живых узлов
CREATE INDEX IF NOT EXISTS idx_clusters_status ON clusters(status);

-- 2. Добавление cluster_id в основные таблицы
-- Мы используем UUID для кластеров

-- В знания
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='knowledge_nodes' AND column_name='cluster_id') THEN
        ALTER TABLE knowledge_nodes ADD COLUMN cluster_id UUID REFERENCES clusters(id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='knowledge_nodes' AND column_name='version') THEN
        ALTER TABLE knowledge_nodes ADD COLUMN version BIGINT DEFAULT 1;
    END IF;
END $$;

-- В задачи
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='tasks' AND column_name='cluster_id') THEN
        ALTER TABLE tasks ADD COLUMN cluster_id UUID REFERENCES clusters(id);
    END IF;
END $$;

-- 3. Регистрация текущего (локального) кластера, если его нет
-- В реальной системе имя и URL берутся из ENV
INSERT INTO clusters (name, url, is_local, status)
VALUES ('mac-studio-primary', 'http://localhost:8081', true, 'active')
ON CONFLICT (name) DO UPDATE SET last_heartbeat = CURRENT_TIMESTAMP;

-- Комментарии для документации
COMMENT ON TABLE clusters IS 'Реестр физических узлов (кластеров) корпорации Singularity';
COMMENT ON COLUMN knowledge_nodes.cluster_id IS 'ID кластера, где был создан или синхронизирован этот узел знаний';
COMMENT ON COLUMN tasks.cluster_id IS 'ID кластера, ответственного за выполнение задачи';
