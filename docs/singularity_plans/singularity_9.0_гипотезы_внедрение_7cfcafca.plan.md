---
name: Singularity 9.0 Гипотезы Внедрение
overview: "План внедрения 4 ключевых гипотез Singularity 9.0: Tacit Knowledge Extractor (стилевое совпадение > 0.85), Emotional Response Modulation (удовлетворенность ↑ 15%), Code-Smell Predictor (precision > 70%, recall > 60%), Predictive Compression (latency ↓ 30%). Каждый компонент интегрируется в существующую архитектуру с A/B тестированием и автоматическим сбором метрик."
todos:
  - id: tacit_knowledge_miner
    content: Создать модуль tacit_knowledge_miner.py для анализа стилевых предпочтений пользователя
    status: completed
  - id: tacit_knowledge_tables
    content: Создать таблицу user_style_profiles в БД для хранения стилевых профилей
    status: completed
  - id: tacit_knowledge_integration
    content: Интегрировать Tacit Knowledge Extractor в ai_core.py для применения стилевых профилей
    status: completed
    dependencies:
      - tacit_knowledge_miner
      - tacit_knowledge_tables
  - id: emotion_detector
    content: Создать модуль emotion_detector.py для детекции эмоций из текста запроса
    status: completed
  - id: emotion_tables
    content: Создать таблицу emotion_logs в БД для хранения данных об эмоциональной адаптации
    status: completed
  - id: emotion_integration
    content: Интегрировать Emotional Response Modulation в ai_core.py для адаптации стиля ответа
    status: completed
    dependencies:
      - emotion_detector
      - emotion_tables
  - id: code_smell_predictor
    content: Создать модуль code_smell_predictor.py для предсказания будущих багов в коде
    status: completed
  - id: code_smell_tables
    content: Создать таблицы code_smell_predictions и code_smell_training_data в БД
    status: completed
  - id: code_smell_model_trainer
    content: Создать модуль code_smell_model_trainer.py для обучения ML модели предсказания багов
    status: completed
    dependencies:
      - code_smell_predictor
      - code_smell_tables
  - id: code_smell_integration
    content: Интегрировать Code-Smell Predictor с code_auditor.py и smart_worker_autonomous.py
    status: completed
    dependencies:
      - code_smell_predictor
      - code_smell_model_trainer
  - id: predictive_compression_enhance
    content: Расширить context_analyzer.py методами предсказания и предсжатия контекста
    status: completed
  - id: predictive_compression_integration
    content: Интегрировать Predictive Compression в ai_core.py и PredictiveCache
    status: completed
    dependencies:
      - predictive_compression_enhance
  - id: ab_testing_setup
    content: Настроить A/B тестирование для всех 4 гипотез через prompt_ab_testing.py
    status: completed
    dependencies:
      - tacit_knowledge_integration
      - emotion_integration
      - predictive_compression_integration
  - id: metrics_dashboard
    content: Добавить секцию Singularity 9.0 Метрики в dashboard/app.py
    status: completed
    dependencies:
      - ab_testing_setup
  - id: metrics_validation
    content: Создать скрипт validate_singularity_9_metrics.py для автоматической валидации целевых метрик
    status: completed
    dependencies:
      - metrics_dashboard
---

# План внедрения Singularity 9.0: 4 ключевые гипотезы

## Целевые метрики успеха

1. **Tacit Knowledge Extractor**: стилевое совпадение > 0.85 (cosine similarity)
2. **Emotional Response Modulation**: удовлетворенность ↑ 15% (через feedback_score)
3. **Code-Smell Predictor**: precision > 70%, recall > 60%
4. **Predictive Compression**: latency ↓ 30% (среднее время ответа)

---

## Этап 1: Tacit Knowledge Extractor (3 дня)

### Задача 1.1: Создание модуля `tacit_knowledge_miner.py`

**Файл:** `knowledge_os/app/tacit_knowledge_miner.py`**Функционал:**

- Анализ паттернов из `interaction_logs` и `knowledge_nodes`
- Извлечение стилевых предпочтений (naming conventions, error handling, testing style)
- Создание стилевого профиля пользователя (`user_style_profiles` таблица)
- Генерация кода в стиле пользователя

**Интеграция:**

- Использовать `enhanced_expert_evolver.py` для получения метрик экспертов
- Использовать `semantic_cache.py` для вычисления similarity между стилями
- Сохранять профили в БД: таблица `user_style_profiles` (user_id, style_vector, preferences JSONB)

### Задача 1.2: Интеграция в `ai_core.py`

**Файл:** `knowledge_os/app/ai_core.py`**Изменения:**

- В `run_smart_agent_async()` добавить проверку стилевого профиля пользователя
- Модифицировать промпт эксперта с учетом стиля пользователя
- Использовать стилевой профиль при генерации кода

**Место интеграции:** После получения `user_part`, перед вызовом эксперта

### Задача 1.3: Создание таблицы `user_style_profiles`

**Файл:** `knowledge_os/migrations/add_tacit_knowledge_tables.sql`**Структура:**

```sql
CREATE TABLE IF NOT EXISTS user_style_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_identifier VARCHAR(255) NOT NULL,
    style_vector FLOAT[],  -- Embedding вектора стиля
    preferences JSONB,     -- {naming_convention, error_handling, testing_style, ...}
    similarity_score FLOAT,  -- Cosine similarity с эталонным стилем
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_style_profiles_user ON user_style_profiles(user_identifier);
CREATE INDEX idx_user_style_profiles_similarity ON user_style_profiles(similarity_score DESC);
```



### Задача 1.4: Сбор метрик стилевого совпадения

**Файл:** `knowledge_os/app/tacit_knowledge_miner.py`**Метрики:**

- `style_similarity_score`: cosine similarity между сгенерированным кодом и стилем пользователя
- Сохранение в `interaction_logs.metadata->>'style_similarity'`
- A/B тестирование: с стилем vs без стиля

### Задача 1.5: Cron job для обновления профилей

**Файл:** `infrastructure/cron/tacit_knowledge_updater.cron`**Расписание:** Ежедневно в 02:00

```cron
0 2 * * * cd /root/knowledge_os && python3 -c "from app.tacit_knowledge_miner import update_style_profiles; import asyncio; asyncio.run(update_style_profiles())" >> logs/tacit_knowledge.log 2>&1
```

---

## Этап 2: Emotional Response Modulation (5 дней)

### Задача 2.1: Создание модуля `emotion_detector.py`

**Файл:** `knowledge_os/app/emotion_detector.py`**Функционал:**

- Детекция эмоций из текста запроса (frustrated, rushed, curious, calm)
- Анализ паттернов (пунктуация, ключевые слова, история взаимодействий)
- Определение эмоционального профиля запроса

**Emotion Profiles:**

```python
EMOTION_PROFILES = {
    "frustrated": {"tone": "calm, supportive", "detail_level": "high", "examples": "more"},
    "rushed": {"tone": "concise, direct", "detail_level": "medium", "examples": "bullet_points"},
    "curious": {"tone": "enthusiastic, detailed", "detail_level": "very_high", "examples": "with_analogies"},
    "calm": {"tone": "professional, clear", "detail_level": "normal", "examples": "standard"}
}
```



### Задача 2.2: Интеграция в `ai_core.py`

**Файл:** `knowledge_os/app/ai_core.py`**Изменения:**

- В `run_smart_agent_async()` детектировать эмоцию перед генерацией ответа
- Модифицировать системный промпт эксперта с учетом эмоции
- Адаптировать стиль ответа (tone, detail_level, examples)

**Место интеграции:** После получения `user_part`, перед вызовом эксперта

### Задача 2.3: Создание таблицы `emotion_logs`

**Файл:** `knowledge_os/migrations/add_emotion_tables.sql`**Структура:**

```sql
CREATE TABLE IF NOT EXISTS emotion_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_log_id UUID REFERENCES interaction_logs(id),
    detected_emotion VARCHAR(50),  -- frustrated, rushed, curious, calm
    emotion_confidence FLOAT,      -- 0.0-1.0
    tone_used VARCHAR(100),        -- calm_supportive, concise_direct, etc.
    detail_level VARCHAR(50),      -- high, medium, very_high, normal
    feedback_score INTEGER,        -- Связь с feedback_score из interaction_logs
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_emotion_logs_interaction ON emotion_logs(interaction_log_id);
CREATE INDEX idx_emotion_logs_emotion ON emotion_logs(detected_emotion);
```



### Задача 2.4: Сбор метрик удовлетворенности

**Файл:** `knowledge_os/app/emotion_detector.py`**Метрики:**

- `satisfaction_delta`: изменение `feedback_score` после применения эмоциональной адаптации
- Сравнение A/B: с эмоциональной адаптацией vs без
- Целевая метрика: удовлетворенность ↑ 15% (через `feedback_score`)

**A/B тестирование:**

- 50% запросов получают эмоциональную адаптацию (variant A)
- 50% запросов получают стандартный ответ (variant B)
- Сравнение `feedback_score` между группами

### Задача 2.5: Интеграция с `prompt_ab_testing.py`

**Файл:** `knowledge_os/app/prompt_ab_testing.py`**Изменения:**

- Добавить поддержку A/B тестов для эмоциональной адаптации
- Использовать существующую инфраструктуру `PromptABTesting` для сбора метрик

---

## Этап 3: Code-Smell Predictor (7 дней)

### Задача 3.1: Создание модуля `code_smell_predictor.py`

**Файл:** `knowledge_os/app/code_smell_predictor.py`**Функционал:**

- Анализ кода на анти-паттерны (cyclomatic complexity, null pointers, race conditions)
- Предсказание вероятности бага в следующие 30 дней
- Интеграция с `code_auditor.py` для создания задач на исправление

**Модель предсказания:**

- Feature engineering: code complexity, history, test coverage, patterns
- ML модель: LightGBM/XGBoost (аналогично `ml_router_model.py`)
- Training data: исторические баги из `code_auditor` задач

### Задача 3.2: Интеграция с `code_auditor.py`

**Файл:** `knowledge_os/app/code_auditor.py`**Изменения:**

- Использовать `CodeSmellPredictor` для предсказания будущих проблем
- Создавать задачи с меткой `bug_probability` в `tasks.metadata`
- Фильтровать задачи по `bug_probability > 0.5`

### Задача 3.3: Создание таблиц для обучения модели

**Файл:** `knowledge_os/migrations/add_code_smell_tables.sql`**Структура:**

```sql
CREATE TABLE IF NOT EXISTS code_smell_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path VARCHAR(500),
    code_snippet TEXT,
    predicted_issues JSONB,  -- {bug_probability, likely_issues, risk_files}
    actual_bugs INTEGER DEFAULT 0,  -- Подтвержденные баги (через 30 дней)
    precision_score FLOAT,   -- Точность предсказания
    recall_score FLOAT,      -- Полнота предсказания
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS code_smell_training_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path VARCHAR(500),
    code_features JSONB,  -- {complexity, patterns, coverage, ...}
    actual_bug BOOLEAN,   -- Был ли баг в следующие 30 дней
    bug_type VARCHAR(100), -- null_pointer, race_condition, etc.
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_code_smell_predictions_file ON code_smell_predictions(file_path);
CREATE INDEX idx_code_smell_training_bug ON code_smell_training_data(actual_bug);
```



### Задача 3.4: Обучение ML модели

**Файл:** `knowledge_os/app/code_smell_model_trainer.py`**Функционал:**

- Сбор данных из `code_smell_training_data`
- Feature engineering (code complexity, history, patterns)
- Обучение LightGBM/XGBoost модели (аналогично `ml_router_trainer.py`)
- Валидация: precision > 70%, recall > 60%

### Задача 3.5: Интеграция в `smart_worker_autonomous.py`

**Файл:** `knowledge_os/app/smart_worker_autonomous.py`**Изменения:**

- При обработке задач от `code_auditor` использовать предсказания `CodeSmellPredictor`
- Приоритизировать задачи с высокой `bug_probability`
- Сохранять метрики precision/recall после подтверждения багов

---

## Этап 4: Predictive Context Compression (5 дней)

### Задача 4.1: Расширение `context_analyzer.py`

**Файл:** `knowledge_os/app/context_analyzer.py`**Функционал:**

- Предсказание следующих запросов на основе истории
- Заранее сжимать релевантные части контекста
- Использовать `PredictiveCache` для предзагрузки контекста

**Методы:**

- `predict_next_query()`: предсказание следующего запроса
- `precompress_context()`: предварительное сжатие контекста
- `get_precompressed_context()`: получение предсжатого контекста

### Задача 4.2: Интеграция с `PredictiveCache`

**Файл:** `knowledge_os/app/optimizers.py`**Изменения:**

- В `PredictiveCache` добавить метод `precompress_context_for_predicted_queries()`
- Использовать `ContextAnalyzer` для предварительного сжатия
- Сохранять предсжатый контекст в кэше

### Задача 4.3: Интеграция в `ai_core.py`

**Файл:** `knowledge_os/app/ai_core.py`**Изменения:**

- Перед обработкой запроса проверять предсжатый контекст в `PredictiveCache`
- Если контекст предсжат, использовать его (снижение latency)
- Измерять `response_time_ms` для метрик

**Место интеграции:** Перед `ContextAnalyzer.compress_context()` (если существует)

### Задача 4.4: Сбор метрик latency

**Файл:** `knowledge_os/app/context_analyzer.py`**Метрики:**

- `latency_before_compression`: время ответа без предсжатия
- `latency_after_compression`: время ответа с предсжатием
- `latency_reduction`: процент снижения latency
- Целевая метрика: latency ↓ 30%

**Сохранение:**

- В `interaction_logs.metadata->>'latency_reduction'`
- A/B тестирование: с предсжатием vs без

### Задача 4.5: Cron job для предсжатия контекста

**Файл:** `infrastructure/cron/predictive_compression.cron`**Расписание:** Каждые 30 минут

```cron
*/30 * * * * cd /root/knowledge_os && python3 -c "from app.context_analyzer import run_predictive_compression; import asyncio; asyncio.run(run_predictive_compression())" >> logs/predictive_compression.log 2>&1
```

---

## Этап 5: Интеграция и тестирование (3 дня)

### Задача 5.1: Создание общего A/B тестирования

**Файл:** `knowledge_os/app/singularity_9_ab_tester.py`**Функционал:**

- Централизованное A/B тестирование всех 4 гипотез
- Сбор метрик из всех компонентов
- Автоматический выбор победителя (на основе целевых метрик)

### Задача 5.2: Dashboard для мониторинга метрик

**Файл:** `knowledge_os/dashboard/app.py`**Изменения:**

- Добавить новую секцию "Singularity 9.0 Метрики"
- Отображение метрик:
- Tacit Knowledge: средний `style_similarity_score`
- Emotional Modulation: изменение `feedback_score`
- Code-Smell Predictor: precision/recall
- Predictive Compression: `latency_reduction`

### Задача 5.3: Автоматическая валидация метрик

**Файл:** `knowledge_os/scripts/validate_singularity_9_metrics.py`**Функционал:**

- Проверка достижения целевых метрик каждые 24 часа
- Отчет в `notifications` при достижении/недостижении метрик
- Автоматическое отключение компонента, если метрики не достигаются

---

## Порядок реализации

### Спринт 1 (3 дня): Tacit Knowledge Extractor

- Задачи 1.1-1.5
- Цель: стилевое совпадение > 0.85

### Спринт 2 (5 дней): Emotional Response Modulation

- Задачи 2.1-2.5
- Цель: удовлетворенность ↑ 15%

### Спринт 3 (7 дней): Code-Smell Predictor

- Задачи 3.1-3.5
- Цель: precision > 70%, recall > 60%

### Спринт 4 (5 дней): Predictive Compression

- Задачи 4.1-4.5
- Цель: latency ↓ 30%

### Спринт 5 (3 дня): Интеграция и тестирование

- Задачи 5.1-5.3
- Цель: валидация всех метрик

---

## Зависимости

- **Tacit Knowledge**: использует `semantic_cache.py`, `enhanced_expert_evolver.py`
- **Emotional Modulation**: использует `prompt_ab_testing.py`, `interaction_logs`
- **Code-Smell Predictor**: использует `code_auditor.py`, `ml_router_model.py` (как пример)
- **Predictive Compression**: использует `context_analyzer.py`, `PredictiveCache`, `optimizers.py`

---

## Критерии успеха

1. **Tacit Knowledge**: `style_similarity_score >= 0.85` (через 7 дней A/B теста)
2. **Emotional Modulation**: `feedback_score` увеличение на 15% (через 7 дней A/B теста)
3. **Code-Smell Predictor**: `precision >= 0.70` и `recall >= 0.60` (через 30 дней обучения)
4. **Predictive Compression**: `latency_reduction >= 0.30` (через 7 дней A/B теста)

---

## Риски и митигация

1. **Tacit Knowledge**: низкая точность стилевого профиля → использование большего объема данных из истории