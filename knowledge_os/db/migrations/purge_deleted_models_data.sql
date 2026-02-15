-- Удаление накопленных данных по моделям, которые больше не используются (70b/104b/32b в MLX удалены).
-- После удаления модели нет смысла хранить аналитику и результаты валидации по ней.
-- См. docs/CHANGES_FROM_OTHER_CHATS.md §0.4ce

-- Список имён удалённых моделей (единый для всех окружений)
-- deepseek-r1-distill-llama:70b, llama3.3:70b, command-r-plus:104b, qwen2.5-coder:32b (из MLX)

DELETE FROM model_analytics
WHERE model_name IN (
    'deepseek-r1-distill-llama:70b',
    'llama3.3:70b',
    'command-r-plus:104b',
    'qwen2.5-coder:32b'
);

DELETE FROM model_validation_results
WHERE model_name IN (
    'deepseek-r1-distill-llama:70b',
    'llama3.3:70b',
    'command-r-plus:104b',
    'qwen2.5-coder:32b'
);

-- Узлы базы знаний по этим моделям (домен "AI Models") можно удалить скриптом:
-- knowledge_os/scripts/purge_deleted_models_knowledge.py
