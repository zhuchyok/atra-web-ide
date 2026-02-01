-- Seed data for Singularity 9.0 Metrics (для дашборда)
-- Заполняет тестовые данные для отображения метрик пока реальные данные не накоплены

-- 1. Tacit Knowledge: interaction_logs с style_similarity в metadata
INSERT INTO interaction_logs (expert_id, user_query, assistant_response, metadata, created_at)
SELECT 
    (SELECT id FROM experts LIMIT 1),
    'Тест tacit knowledge',
    'def example(): pass',
    jsonb_build_object('style_similarity', 0.92, 'source', 'seed'),
    NOW() - (random() * 6 || ' days')::interval
FROM generate_series(1, 5);

-- 2. Predictive Compression: interaction_logs с latency_reduction в metadata
INSERT INTO interaction_logs (expert_id, user_query, assistant_response, metadata, created_at)
SELECT 
    (SELECT id FROM experts LIMIT 1),
    'Тест compression',
    'Ответ',
    jsonb_build_object('latency_reduction', 0.35, 'source', 'seed'),
    NOW() - (random() * 6 || ' days')::interval
FROM generate_series(1, 5);

-- 3. Code-Smell Predictor (требует таблицу из add_code_smell_tables.sql)
INSERT INTO code_smell_predictions (file_path, code_snippet, predicted_issues, precision_score, recall_score, created_at)
SELECT 
    'src/test_' || i || '.py',
    'def foo(): pass',
    '{"bug_probability": 0.1, "likely_issues": []}'::jsonb,
    0.75 + random() * 0.15,
    0.70 + random() * 0.15,
    NOW() - (random() * 29 || ' days')::interval
FROM generate_series(1, 5) i;

-- 4. Emotional Response Modulation: interaction_logs с feedback + emotion_logs
-- A: с эмоцией (emotion_logs) — выше feedback; B: без эмоции — baseline
DO $$
DECLARE
    exp_id UUID;
    il_id INTEGER;
    i INT;
BEGIN
    SELECT id INTO exp_id FROM experts LIMIT 1;
    IF exp_id IS NULL THEN RETURN; END IF;
    
    -- Базовый вариант B (без emotion_logs, смешанный feedback для avg < 1)
    INSERT INTO interaction_logs (expert_id, user_query, assistant_response, feedback_score, created_at)
    VALUES (exp_id, 'Тест baseline', 'Ответ', 1, NOW() - '1 day'::interval);
    INSERT INTO interaction_logs (expert_id, user_query, assistant_response, feedback_score, created_at)
    VALUES (exp_id, 'Тест baseline', 'Ответ', -1, NOW() - '2 days'::interval);
    INSERT INTO interaction_logs (expert_id, user_query, assistant_response, feedback_score, created_at)
    VALUES (exp_id, 'Тест baseline', 'Ответ', 1, NOW() - '3 days'::interval);
    
    -- Вариант A (с emotion_logs, feedback выше)
    FOR i IN 1..5 LOOP
        INSERT INTO interaction_logs (expert_id, user_query, assistant_response, feedback_score, created_at)
        VALUES (exp_id, 'Тест emotion', 'Ответ с эмоцией', 1, NOW() - (random() * 6 || ' days')::interval)
        RETURNING id INTO il_id;
        
        INSERT INTO emotion_logs (interaction_log_id, detected_emotion, emotion_confidence, tone_used, feedback_score, created_at)
        VALUES (il_id::text, 'curious', 0.9, 'calm_supportive', 1, NOW());  -- interaction_log_id TEXT
    END LOOP;
END $$;
