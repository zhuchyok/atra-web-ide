---
name: "Singularity 5.0: Полный план оптимизаций"
overview: "Реализация всех 6 приоритетных гипотез для улучшения системы: интеллектуальный роутинг, параллельная обработка, адаптивное обучение, умное сокращение контекста, мультимодальность и стриминг ответов."
todos:
  - id: sprint1_data_collection
    content: "Спринт 1.1: Создать ml_router_data_collector.py и интегрировать сбор данных о решениях роутера"
    status: completed
  - id: sprint1_model_training
    content: "Спринт 1.2: Создать ml_router_model.py и ml_router_trainer.py для обучения ML-модели"
    status: completed
    dependencies:
      - sprint1_data_collection
  - id: sprint1_integration
    content: "Спринт 1.3: Интегрировать ML-модель в local_router.py и ai_core.py"
    status: completed
    dependencies:
      - sprint1_model_training
  - id: sprint1_ab_testing
    content: "Спринт 1.4: Создать систему A/B тестирования для валидации ML-роутинга"
    status: completed
    dependencies:
      - sprint1_integration
  - id: sprint2_batch_processing
    content: "Спринт 2.1: Создать batch_processor.py и интегрировать batch processing"
    status: completed
  - id: sprint2_load_balancing
    content: "Спринт 2.2: Создать load_balancer.py и интегрировать load balancing"
    status: completed
  - id: sprint2_parallel_processing
    content: "Спринт 2.3: Расширить parallel_processor и интегрировать параллельную обработку"
    status: completed
    dependencies:
      - sprint2_batch_processing
      - sprint2_load_balancing
  - id: sprint3_feedback_collection
    content: "Спринт 3.1: Создать feedback_collector.py и интегрировать сбор feedback"
    status: completed
  - id: sprint3_adaptive_learning
    content: "Спринт 3.2: Создать adaptive_learner.py и интегрировать автоматическое обновление примеров"
    status: completed
    dependencies:
      - sprint3_feedback_collection
  - id: sprint3_monitoring
    content: "Спринт 3.3: Добавить мониторинг улучшений в enhanced_monitor.py"
    status: completed
    dependencies:
      - sprint3_adaptive_learning
  - id: sprint4_context_analysis
    content: "Спринт 4.1: Создать context_analyzer.py для семантического анализа контекста"
    status: completed
  - id: sprint4_relevance_detection
    content: "Спринт 4.2: Реализовать определение релевантности частей контекста"
    status: completed
    dependencies:
      - sprint4_context_analysis
  - id: sprint4_integration
    content: "Спринт 4.3: Интегрировать умное сокращение контекста в ai_core.py с Quality Gate"
    status: completed
    dependencies:
      - sprint4_relevance_detection
  - id: sprint5_moondream_integration
    content: "Спринт 5.1: Создать vision_processor.py и интегрировать Moondream"
    status: completed
  - id: sprint5_image_processing
    content: "Спринт 5.2: Реализовать обработку изображений (скриншоты, диаграммы)"
    status: completed
    dependencies:
      - sprint5_moondream_integration
  - id: sprint5_quality_testing
    content: "Спринт 5.3: Добавить тестирование качества анализа изображений"
    status: completed
    dependencies:
      - sprint5_image_processing
  - id: sprint6_streaming_api
    content: "Спринт 6.1: Создать streaming_processor.py и интегрировать streaming для локальных моделей"
    status: completed
  - id: sprint6_cursor_integration
    content: "Спринт 6.2: Интегрировать streaming в cursor_proxy.py"
    status: completed
    dependencies:
      - sprint6_streaming_api
  - id: sprint6_ux_testing
    content: "Спринт 6.3: Добавить метрики воспринимаемой скорости и UX тестирование"
    status: completed
    dependencies:
      - sprint6_cursor_integration
  - id: database_migrations
    content: Создать миграции БД для новых таблиц (ml_router_training_data, feedback_data, etc.)
    status: completed
  - id: testing_suite
    content: Создать тесты для всех новых модулей
    status: pending
  - id: documentation
    content: Создать документацию для всех новых функций
    status: pending
---

# Singularity 5.0

: Полный план оптимизаций

## Обзор

План включает реализацию 6 приоритетных гипотез для улучшения системы ATRA:

1. Интеллектуальный роутинг (ML-based)
2. Параллельная обработка
3. Адаптивное обучение
4. Умное сокращение контекста
5. Мультимодальность
6. Стриминг ответов

**Ожидаемые результаты:**

- Экономия токенов: до 95%+ (комбинация всех оптимизаций)
- Улучшение скорости: до 500% (комбинация всех оптимизаций)
- Улучшение качества: до 60% (комбинация всех оптимизаций)

---

## Спринт 1: Интеллектуальный роутинг (ML-based)

**Цель:** ML-модель предсказывает оптимальный маршрут (local/cloud) на основе типа задачи, истории и контекста.**Ожидаемый эффект:**

- Экономия токенов: +10-15%
- Улучшение качества: +5-10%
- Улучшение скорости: +20-30%

### Этап 1.1: Сбор данных для обучения

**Файлы:**

- `knowledge_os/app/ml_router_data_collector.py` (новый)
- `knowledge_os/app/local_router.py` (модификация)
- `knowledge_os/app/ai_core.py` (модификация)

**Задачи:**

1. Создать `ml_router_data_collector.py` для сбора данных о решениях роутера:

- Тип задачи (coding, reasoning, general)
- Длина промпта
- Категория (из `category` параметра)
- Выбранный маршрут (local_mac, local_server, cloud)
- Результат (performance_score, tokens_saved, latency)
- Качество ответа (из Quality Assurance)

2. Модифицировать `local_router.py`:

- Добавить логирование решений роутера в БД
- Сохранять контекст решения (features)

3. Модифицировать `ai_core.py`:

- Интегрировать сбор данных после каждого роутинга
- Сохранять метрики результата

**Критерии успеха:**

- Собрано минимум 1000 примеров решений роутера
- Данные включают все необходимые features
- Данные сохраняются в БД (таблица `ml_router_training_data`)

### Этап 1.2: Обучение ML-модели

**Файлы:**

- `knowledge_os/app/ml_router_trainer.py` (новый)
- `knowledge_os/app/ml_router_model.py` (новый)

**Задачи:**

1. Создать `ml_router_model.py`:

- Класс `MLRouterModel` с методами `predict()` и `train()`
- Использовать LightGBM или XGBoost
- Features: тип задачи, длина промпта, категория, история успешности узлов
- Target: оптимальный маршрут (local_mac, local_server, cloud)

2. Создать `ml_router_trainer.py`:

- Скрипт для обучения модели на собранных данных
- Валидация (train/test split)
- Метрики: accuracy, precision, recall, F1
- Сохранение модели в файл

**Критерии успеха:**

- Точность предсказания > 85%
- F1-score > 0.80
- Модель сохранена и готова к использованию

### Этап 1.3: Интеграция ML-модели в роутер

**Файлы:**

- `knowledge_os/app/local_router.py` (модификация)
- `knowledge_os/app/ai_core.py` (модификация)

**Задачи:**

1. Модифицировать `local_router.py`:

- Добавить метод `predict_optimal_route()` с использованием ML-модели
- Интегрировать предсказание в `run_local_llm()`
- Fallback на эвристический роутинг если модель недоступна

2. Модифицировать `ai_core.py`:

- Использовать ML-предсказание перед выбором маршрута
- Логировать использование ML vs эвристики

**Критерии успеха:**

- ML-модель интегрирована в роутинг
- Fallback работает корректно
- Логирование работает

### Этап 1.4: A/B тестирование

**Файлы:**

- `knowledge_os/app/ml_router_ab_test.py` (новый)
- `knowledge_os/app/enhanced_monitor.py` (модификация)

**Задачи:**

1. Создать `ml_router_ab_test.py`:

- Система A/B тестирования (50% ML, 50% эвристика)
- Сравнение метрик: экономия токенов, качество, скорость
- Автоматический выбор лучшей стратегии

2. Модифицировать `enhanced_monitor.py`:

- Добавить метрики A/B тестирования
- Dashboard для сравнения стратегий

**Критерии успеха:**

- A/B тестирование работает
- Метрики собираются и анализируются
- Экономия токенов > 10%
- Качество не снижается

---

## Спринт 2: Параллельная обработка

**Цель:** Параллельная обработка нескольких запросов на разных узлах для ускорения системы.**Ожидаемый эффект:**

- Улучшение скорости: +200-300%
- Лучшее использование ресурсов
- Масштабируемость

### Этап 2.1: Batch Processing

**Файлы:**

- `knowledge_os/app/batch_processor.py` (новый)
- `knowledge_os/app/ai_core.py` (модификация)

**Задачи:**

1. Создать `batch_processor.py`:

- Класс `BatchProcessor` для объединения множественных запросов
- Очередь запросов с timeout
- Объединение похожих запросов в один промпт
- Распределение по узлам

2. Модифицировать `ai_core.py`:

- Интегрировать batch processing для множественных запросов
- Определение возможности batch (похожие запросы)

**Критерии успеха:**

- Batch processing работает
- Экономия токенов на batch запросах > 15%
- Качество не снижается

### Этап 2.2: Load Balancing

**Файлы:**

- `knowledge_os/app/load_balancer.py` (новый)
- `knowledge_os/app/local_router.py` (модификация)

**Задачи:**

1. Создать `load_balancer.py`:

- Распределение нагрузки между узлами
- Учет текущей загрузки узлов
- Round-robin с учетом производительности

2. Модифицировать `local_router.py`:

- Интегрировать load balancer
- Мониторинг загрузки узлов

**Критерии успеха:**

- Load balancing работает
- Равномерное распределение нагрузки
- Использование всех доступных узлов

### Этап 2.3: Параллельная обработка

**Файлы:**

- `knowledge_os/app/parallel_processor.py` (новый, уже есть в optimizers.py)
- `knowledge_os/app/ai_core.py` (модификация)

**Задачи:**

1. Расширить `optimizers.py`:

- Улучшить `ParallelProcessor` для реальной параллельной обработки
- Семафоры для контроля нагрузки
- Обработка нескольких запросов одновременно

2. Модифицировать `ai_core.py`:

- Использовать параллельную обработку для множественных запросов
- Интеграция с batch processing

**Критерии успеха:**

- Скорость обработки batch > 2x
- Качество не снижается
- Стабильность системы

---

## Спринт 3: Адаптивное обучение

**Цель:** Система автоматически улучшает качество ответов через обучение на feedback и ошибках.**Ожидаемый эффект:**

- Улучшение качества: +20-30% за месяц
- Снижение количества reroute в облако
- Экономия токенов: +5-10%

### Этап 3.1: Сбор feedback

**Файлы:**

- `knowledge_os/app/feedback_collector.py` (новый)
- `knowledge_os/app/ai_core.py` (модификация)

**Задачи:**

1. Создать `feedback_collector.py`:

- Сбор явного feedback (если будет API)
- Сбор неявного feedback (reroute в облако = негативный)
- Сохранение feedback в БД

2. Модифицировать `ai_core.py`:

- Логировать случаи reroute в облако
- Сохранять причины reroute (low quality, safety check failed)

**Критерии успеха:**

- Feedback собирается автоматически
- Данные сохраняются в БД
- Можно анализировать паттерны ошибок

### Этап 3.2: Автоматическое обновление примеров

**Файлы:**

- `knowledge_os/app/adaptive_learner.py` (новый)
- `knowledge_os/app/distillation_engine.py` (модификация)

**Задачи:**

1. Создать `adaptive_learner.py`:

- Анализ feedback и ошибок
- Автоматическое обновление примеров в distillation engine
- Приоритизация примеров на основе успешности

2. Модифицировать `distillation_engine.py`:

- Интеграция с adaptive_learner
- Автоматическое удаление неэффективных примеров
- Добавление новых успешных примеров

**Критерии успеха:**

- Примеры обновляются автоматически
- Качество улучшается на 5% в неделю
- Количество reroute снижается на 20%

### Этап 3.3: Мониторинг улучшений

**Файлы:**

- `knowledge_os/app/enhanced_monitor.py` (модификация)
- `knowledge_os/app/local_mind_dashboard.py` (модификация)

**Задачи:**

1. Модифицировать `enhanced_monitor.py`:

- Метрики качества ответов во времени
- Тренды улучшения
- Анализ эффективности примеров

2. Модифицировать `local_mind_dashboard.py`:

- Dashboard для мониторинга адаптивного обучения
- Графики улучшения качества

**Критерии успеха:**

- Метрики собираются и визуализируются
- Можно отслеживать прогресс обучения

---

## Спринт 4: Умное сокращение контекста

**Цель:** Интеллектуальное сокращение контекста (удаление нерелевантных частей) для экономии токенов.**Ожидаемый эффект:**

- Экономия токенов: +20-30%
- Улучшение скорости: +10-15%
- Сохранение качества

### Этап 4.1: Семантический анализ контекста

**Файлы:**

- `knowledge_os/app/context_analyzer.py` (новый)
- `knowledge_os/app/context_compressor.py` (модификация)

**Задачи:**

1. Создать `context_analyzer.py`:

- Семантический анализ контекста (использовать эмбеддинги)
- Определение релевантности частей контекста к запросу
- Ранжирование частей по релевантности

2. Модифицировать `context_compressor.py`:

- Интеграция с context_analyzer
- Умное удаление нерелевантных частей
- Сохранение важных частей

**Критерии успеха:**

- Релевантность определяется корректно
- Важные части сохраняются
- Нерелевантные части удаляются

### Этап 4.2: Определение релевантности

**Файлы:**

- `knowledge_os/app/context_analyzer.py` (расширение)

**Задачи:**

1. Расширить `context_analyzer.py`:

- Использовать эмбеддинги для определения схожести
- Порог релевантности (настраиваемый)
- Сохранение структуры (не разрывать логические блоки)

**Критерии успеха:**

- Релевантность определяется с точностью > 80%
- Структура контекста сохраняется

### Этап 4.3: Интеграция в ai_core

**Файлы:**

- `knowledge_os/app/ai_core.py` (модификация)
- `knowledge_os/app/quality_assurance.py` (модификация)

**Задачи:**

1. Модифицировать `ai_core.py`:

- Использовать умное сокращение контекста перед отправкой в облако
- Quality Gate для проверки сохранения качества

2. Модифицировать `quality_assurance.py`:

- Проверка сохранения релевантности после сокращения
- Валидация качества ответа после сокращения

**Критерии успеха:**

- Экономия токенов > 20%
- Качество не снижается
- Релевантность сохраняется

---

## Спринт 5: Мультимодальность

**Цель:** Обработка изображений локальными моделями для расширения возможностей без токенов.**Ожидаемый эффект:**

- Новые возможности (анализ скриншотов, диаграмм)
- Экономия токенов: 100% на изображениях
- Расширение функциональности

### Этап 5.1: Интеграция Moondream

**Файлы:**

- `knowledge_os/app/vision_processor.py` (новый)
- `knowledge_os/app/local_router.py` (модификация)

**Задачи:**

1. Создать `vision_processor.py`:

- Класс `VisionProcessor` для обработки изображений
- Интеграция с Moondream через Ollama
- Методы для анализа изображений (скриншоты, диаграммы)

2. Модифицировать `local_router.py`:

- Добавить поддержку vision моделей
- Роутинг для vision задач

**Критерии успеха:**

- Moondream интегрирован и работает
- Изображения обрабатываются локально
- Экономия токенов 100% на изображениях

### Этап 5.2: Обработка изображений

**Файлы:**

- `knowledge_os/app/vision_processor.py` (расширение)
- `knowledge_os/app/ai_core.py` (модификация)

**Задачи:**

1. Расширить `vision_processor.py`:

- Анализ скриншотов кода
- Анализ диаграмм
- Извлечение текста из изображений
- Описание изображений

2. Модифицировать `ai_core.py`:

- Определение наличия изображений в запросе
- Роутинг на vision processor
- Комбинирование текста и изображений

**Критерии успеха:**

- Качество анализа изображений > 0.7
- Полезность для пользователей
- Стабильность работы

### Этап 5.3: Тестирование качества

**Файлы:**

- `knowledge_os/app/vision_processor.py` (расширение)
- `knowledge_os/app/quality_assurance.py` (модификация)

**Задачи:**

1. Расширить `vision_processor.py`:

- Метрики качества анализа
- Валидация результатов

2. Модифицировать `quality_assurance.py`:

- Проверка качества анализа изображений
- Fallback на облако при низком качестве

**Критерии успеха:**

- Качество анализа > 0.7
- Fallback работает корректно

---

## Спринт 6: Стриминг ответов

**Цель:** Стриминг ответов для улучшения воспринимаемой скорости и UX.**Ожидаемый эффект:**

- Улучшение UX: значительное
- Воспринимаемая скорость: +50-100%
- Лучший user experience

### Этап 6.1: Streaming API для локальных моделей

**Файлы:**

- `knowledge_os/app/streaming_processor.py` (новый)
- `knowledge_os/app/local_router.py` (модификация)

**Задачи:**

1. Создать `streaming_processor.py`:

- Класс `StreamingProcessor` для стриминга ответов
- Интеграция с Ollama streaming API
- Генерация chunks ответа

2. Модифицировать `local_router.py`:

- Добавить поддержку streaming
- Метод `run_local_llm_streaming()`

**Критерии успеха:**

- Streaming работает для локальных моделей
- Chunks генерируются корректно
- Стабильность работы

### Этап 6.2: Интеграция в cursor_proxy

**Файлы:**

- `scripts/cursor_proxy.py` (модификация)
- `knowledge_os/app/ai_core.py` (модификация)

**Задачи:**

1. Модифицировать `cursor_proxy.py`:

- Использовать streaming для локальных моделей
- Формат OpenAI streaming API
- Обработка streaming chunks

2. Модифицировать `ai_core.py`:

- Поддержка streaming режима
- Передача streaming chunks

**Критерии успеха:**

- Streaming работает в Cursor
- UX улучшен
- Воспринимаемая скорость улучшена

### Этап 6.3: UX тестирование

**Файлы:**

- `knowledge_os/app/enhanced_monitor.py` (модификация)

**Задачи:**

1. Модифицировать `enhanced_monitor.py`:

- Метрики воспринимаемой скорости
- Анализ UX улучшений

**Критерии успеха:**

- Воспринимаемая скорость улучшена на 50-100%
- UX улучшен
- Пользователи довольны

---

## Общие задачи

### База данных

**Миграции:**

- `knowledge_os/db/migrations/add_ml_router_tables.sql` (новый)
- `knowledge_os/db/migrations/add_feedback_tables.sql` (новый)

**Таблицы:**

- `ml_router_training_data` - данные для обучения ML-модели
- `ml_router_predictions` - предсказания модели
- `feedback_data` - feedback от пользователей
- `adaptive_learning_logs` - логи адаптивного обучения

### Тестирование

**Файлы:**

- `tests/test_ml_router.py` (новый)
- `tests/test_batch_processor.py` (новый)
- `tests/test_adaptive_learner.py` (новый)
- `tests/test_context_analyzer.py` (новый)
- `tests/test_vision_processor.py` (новый)
- `tests/test_streaming.py` (новый)

### Документация

**Файлы:**

- `docs/ML_ROUTER_IMPLEMENTATION.md` (новый)
- `docs/BATCH_PROCESSING.md` (новый)
- `docs/ADAPTIVE_LEARNING.md` (новый)
- `docs/CONTEXT_COMPRESSION.md` (новый)
- `docs/MULTIMODALITY.md` (новый)
- `docs/STREAMING.md` (новый)

---

## Критерии успеха всего плана

1. **Экономия токенов:** до 95%+ (комбинация всех оптимизаций)
2. **Улучшение скорости:** до 500% (комбинация всех оптимизаций)
3. **Улучшение качества:** до 60% (комбинация всех оптимизаций)
4. **Качество не снижается:** все оптимизации проходят через Quality Gate
5. **Стабильность:** система работает стабильно со всеми оптимизациями

---

## Порядок реализации

Рекомендуемый порядок:

1. Спринт 1 (Интеллектуальный роутинг) - основа для остальных
2. Спринт 2 (Параллельная обработка) - можно параллельно со Спринтом 1
3. Спринт 4 (Умное сокращение контекста) - быстрая реализация
4. Спринт 6 (Стриминг ответов) - улучшение UX