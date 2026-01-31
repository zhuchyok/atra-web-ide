# Документация кода Knowledge OS

**Дата генерации:** 2026-01-09 22:17:31

## worker.py

### Функции

#### run_cursor_agent

Run cursor-agent CLI to process a prompt and return output.

**Параметры:** `prompt`

## global_scout.py

Global Scout: Интеграция с внешними API для проверки актуальности знаний

Интегрируется с:
- GitHub (best practices, популярные решения)
- Stack Overflow (проверка решений)
- arXiv (научные публикации)
- Hacker News (тренды в разработке)

### Классы

#### ExternalValidation

Результат валидации знания из внешних источников

#### GitHubScout

Интеграция с GitHub API для проверки best practices

**Методы:**

- `__init__(self, token)`
- `_extract_keywords(self, content, domain)`
  - Извлечение ключевых слов из контента...

#### StackOverflowScout

Интеграция с Stack Overflow API для проверки решений

**Методы:**

- `__init__(self, key)`
- `_extract_keywords(self, content, domain)`
  - Извлечение ключевых слов...

#### ArxivScout

Интеграция с arXiv API для проверки научных публикаций

**Методы:**

- `_parse_arxiv_response(self, xml_text)`
  - Простой парсинг ответа arXiv (упрощенный)...
- `_extract_keywords(self, content, domain)`
  - Извлечение ключевых слов...

#### GlobalScout

Главный класс для интеграции со всеми внешними API

**Методы:**

- `__init__(self)`

## scout_researcher.py

## adversarial_critic.py

### Функции

#### run_cursor_agent

Run cursor-agent CLI to process a prompt and return output.

**Параметры:** `prompt`

## enhanced_monitor.py

Enhanced Monitoring System for Knowledge OS
Расширенная система мониторинга с метриками VDS и автоматическими алертами

### Функции

#### log_message

Логирование в файл

**Параметры:** `message`

## search_ml_trading.py

Скрипт для поиска информации о торговой ML модели в базе знаний

## victoria_morning_report.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

#### send_telegram_msg

**Параметры:** `msg`

## strategic_board.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

## contextual_learner.py

Contextual Learner: Контекстная память и адаптивное обучение

Функционал:
- Запоминание успешных паттернов
- Адаптивное обучение на основе обратной связи
- Персонализация (учет предпочтений пользователей)
- Прогнозирование потребностей

### Классы

#### ContextualPattern

Паттерн контекстной памяти

#### ContextualMemory

Класс для работы с контекстной памятью

**Методы:**

- `__init__(self, db_url)`
- `_hash_context(self, query, domain, expert)`
  - Создание хеша контекста...

#### AdaptiveLearner

Класс для адаптивного обучения на основе обратной связи

**Методы:**

- `__init__(self, db_url)`

#### PersonalizationEngine

Класс для персонализации (учет предпочтений пользователей)

**Методы:**

- `__init__(self, db_url)`

#### NeedPredictor

Класс для прогнозирования потребностей пользователей

**Методы:**

- `__init__(self, db_url)`

## knowledge_graph.py

Knowledge Graph: Управление графом знаний и связями между узлами

Функционал:
- Создание связей между знаниями
- Поиск связанных узлов
- Визуализация графа
- Навигация по связанным знаниям

### Классы

#### LinkType

Типы связей между узлами знаний

#### KnowledgeLink

Связь между узлами знаний

**Методы:**

- `__post_init__(self)`

#### KnowledgeGraph

Класс для работы с графом знаний

**Методы:**

- `__init__(self, db_url)`

## meta_synthesizer.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

## security.py

Security Module: Аутентификация, авторизация и безопасность

Функционал:
- JWT токены для API
- Роли и права доступа
- Аудит действий пользователей
- Шифрование чувствительных данных

### Классы

#### Role

Роли пользователей

#### Permission

Права доступа

#### SecurityManager

Класс для управления безопасностью

**Методы:**

- `__init__(self, db_url)`
- `generate_jwt_token(self, user_id, username, role, expires_in_hours)`
  - Генерация JWT токена...
- `verify_jwt_token(self, token)`
  - Проверка JWT токена...
- `hash_password(self, password)`
  - Хеширование пароля...
- `verify_password(self, password, hashed)`
  - Проверка пароля...
- `encrypt_sensitive_data(self, data)`
  - Шифрование чувствительных данных...
- `decrypt_sensitive_data(self, encrypted_data)`
  - Расшифровка чувствительных данных...
- `has_permission(self, role, permission)`
  - Проверка наличия права доступа...

### Функции

#### require_permission

Декоратор для проверки прав доступа

**Параметры:** `permission`

## radar.py

## enhanced_expert_evolver.py

Enhanced Expert Evolver: Автоматическая эволюция экспертов на основе метрик эффективности

Функционал:
- Метрики эффективности экспертов (success_rate, response_time, knowledge_quality)
- Автоматическая эволюция на основе метрик
- Удаление неэффективных экспертов
- Специализация экспертов (углубление в узкие области)

### Классы

#### ExpertMetrics

Метрики эффективности эксперта

#### ExpertMetricsCollector

Класс для сбора метрик эффективности экспертов

**Методы:**

- `__init__(self, db_url)`

#### ExpertEvolver

Класс для автоматической эволюции экспертов

**Методы:**

- `__init__(self, db_url)`
- `_format_feedback_data(self, feedback_data)`
  - Форматирование данных feedback для промпта...

### Функции

#### run_cursor_agent

Запуск Cursor Agent для генерации контента

**Параметры:** `prompt`

## resource_manager.py

## expert_evolver.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

## process_expert_task.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

## auto_fixer.py

### Функции

#### run_cursor_agent

Run cursor-agent CLI to generate code fixes.

**Параметры:** `prompt`

#### verify_syntax

Verify python syntax using py_compile.

**Параметры:** `file_path`

## expert_generator.py

### Функции

#### run_cursor_agent

Run cursor-agent CLI to process a prompt and return output.

**Параметры:** `prompt`

## guardian.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

## enhanced_immunity.py

Enhanced Immunity System with Auto-Fixing
Расширенная система иммунитета с автоматическим исправлением знаний

### Функции

#### run_cursor_agent

Запуск Cursor Agent для генерации контента

**Параметры:** `prompt, timeout`

## orchestrator.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

## synthetic_generator.py

### Функции

#### run_cursor_agent

Run cursor-agent CLI to process a prompt and return output.

**Параметры:** `prompt`

## enhanced_orchestrator.py

Enhanced Orchestrator v3.1 with Task Prioritization and Workload Balancing
Улучшенный Orchestrator с приоритизацией задач и балансировкой нагрузки

### Функции

#### run_cursor_agent

Запуск Cursor Agent для генерации контента

**Параметры:** `prompt`

## simulator.py

## webhook_manager.py

Webhook Manager: Система webhooks для интеграции с внешними системами

Функционал:
- Webhooks для уведомлений
- Интеграция с Slack, Discord, Telegram
- Автоматические отчеты
- REST API для внешних систем

### Классы

#### WebhookType

Типы webhooks

#### WebhookConfig

Конфигурация webhook

**Методы:**

- `__post_init__(self)`

#### WebhookManager

Класс для управления webhooks

**Методы:**

- `__init__(self, db_url)`
- `_format_slack_message(self, event_type, payload)`
  - Форматирование сообщения для Slack...
- `_format_discord_message(self, event_type, payload)`
  - Форматирование сообщения для Discord...
- `_format_telegram_message(self, event_type, payload)`
  - Форматирование сообщения для Telegram...

#### AutoReporter

Класс для автоматических отчетов

**Методы:**

- `__init__(self, db_url)`

## telegram_gateway.py

## ad_generator.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

## pnl_manager.py

## doc_generator.py

Documentation Generator: Автогенерация документации

Функционал:
- Автогенерация документации из кода (docstrings)
- Автогенерация API документации
- Автогенерация примеров использования
- Интерактивные туториалы

### Классы

#### CodeDocumentationExtractor

Извлечение документации из кода

**Методы:**

- `__init__(self, base_path)`
- `extract_module_docs(self, module_path)`
  - Извлечение документации из модуля...
- `extract_all_modules(self)`
  - Извлечение документации из всех модулей...

#### APIDocumentationGenerator

Генерация API документации

**Методы:**

- `__init__(self, api_file)`
- `generate_openapi_spec(self)`
  - Генерация OpenAPI спецификации...
- `generate_api_docs_markdown(self)`
  - Генерация Markdown документации API...

#### UsageExamplesGenerator

Генерация примеров использования

**Методы:**

- `generate_python_examples(self)`
  - Генерация примеров на Python...
- `generate_curl_examples(self)`
  - Генерация примеров с curl...

#### TutorialGenerator

Генерация интерактивных туториалов

**Методы:**

- `generate_tutorials(self)`
  - Генерация туториалов...

#### DocumentationGenerator

Главный класс для генерации документации

**Методы:**

- `__init__(self, output_dir)`
- `generate_all_docs(self)`
  - Генерация всей документации...
- `_format_code_docs(self, modules)`
  - Форматирование документации кода...
- `_generate_index(self, files)`
  - Генерация индекса документации...

## nightly_learner.py

### Функции

#### run_cursor_agent

**Параметры:** `prompt`

## performance_optimizer.py

Performance Optimizer: Оптимизация производительности запросов

Функционал:
- Кэширование сложных вычислений
- Асинхронная обработка тяжелых задач
- Мониторинг производительности
- Автоматическая оптимизация

### Классы

#### QueryCache

Класс для кэширования результатов запросов

**Методы:**

- `__init__(self, redis_url)`
- `_make_cache_key(self, query, params)`
  - Создание ключа кэша из запроса и параметров...

#### AsyncTaskQueue

Очередь для асинхронной обработки тяжелых задач

**Методы:**

- `__init__(self, db_url)`

#### PerformanceMonitor

Мониторинг производительности запросов

**Методы:**

- `__init__(self, db_url)`

### Функции

#### cached_query

Декоратор для кэширования результатов запросов

**Параметры:** `ttl`

## critic.py

### Классы

#### CriticCore

**Методы:**

- `__init__(self, pool)`

## code_auditor.py

### Функции

#### run_cursor_agent

Run cursor-agent CLI to process a prompt and return output.

**Параметры:** `prompt`

## main.py

## main_enhanced.py

Enhanced MCP Server with Multimodal Search
Улучшенный MCP сервер с мультимодальным поиском

## researcher.py

## knowledge_cleaner.py

## vector_core.py

### Классы

#### TextRequest

#### BatchRequest

#### VectorResponse

#### BatchResponse

## rest_api.py

REST API для внешних систем

Функционал:
- REST API endpoints для работы с Knowledge OS
- Аутентификация через API keys
- Документация через OpenAPI/Swagger

### Классы

#### KnowledgeNodeCreate

#### KnowledgeNodeResponse

#### SearchRequest

#### WebhookCreate

#### LoginRequest

#### RegisterRequest

## evaluator.py

### Функции

#### run_cursor_agent

Run cursor-agent CLI to process a prompt and return output.

**Параметры:** `prompt`

## enhanced_search.py

Enhanced Multimodal Search for Knowledge OS
Улучшенный мультимодальный поиск с поддержкой разных типов запросов

### Классы

#### SearchMode

Режимы поиска

### Функции

#### detect_search_mode

Автоматическое определение режима поиска

**Параметры:** `query`

