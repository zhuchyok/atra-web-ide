---
name: Singularity 2.0 Implementation Plan
overview: Implementation of a three-tier intelligence layer (Evaluator, Tracer, and Agent Gym) to reach Level 4 autonomy (Self-evolving system) according to Google 2025 standards.
todos:
  - id: db-migration-eval
    content: Добавление колонок is_verified и quality_report в БД.
    status: completed
  - id: implement-evaluator-py
    content: Разработка модуля evaluator.py (LM Judge).
    status: completed
  - id: update-researcher-eval
    content: Обновление researcher.py для работы с системой верификации.
    status: completed
  - id: implement-tracing-tg-gateway
    content: Внедрение CoT-трассировки в telegram_gateway.py.
    status: completed
  - id: implement-agent-gym-py
    content: Разработка модуля synthetic_generator.py (Agent Gym).
    status: completed
  - id: setup-cron-singularity
    content: Настройка cron-задач для ночного цикла Сингулярности.
    status: completed
---

# План «Сингулярность 2.0» (Google 2025)

Этот план направлен на трансформацию Knowledge OS в саморазвивающуюся систему путем внедрения автоматической оценки качества знаний, глубокой трассировки рассуждений и синтетической генерации новых идей.

## 1. Слой «LM Judge» (Evaluator)

Цель: Прекратить бесконтрольное добавление знаний и внедрить систему «сертификации» качества.

### Задачи:

- Добавить в таблицу `knowledge_nodes` колонки `is_verified` (boolean) и `quality_report` (jsonb).
- Создать [`knowledge_os/app/evaluator.py`](knowledge_os/app/evaluator.py), который:
    - Выбирает узлы с `is_verified = FALSE`.
    - Использует `cursor-agent` для критического анализа данных по 3 критериям: Достоверность, Актуальность, Полезность.
    - Присваивает финальный `confidence_score` и устанавливает `is_verified = TRUE`.
- Обновить [`knowledge_os/app/researcher.py`](knowledge_os/app/researcher.py), чтобы новые данные из интернета помечались как не верифицированные.

## 2. Слой «Agentic Observability» (Tracer)

Цель: Сохранять «путь мысли» ИИ для отладки и последующего обучения на удачных цепочках рассуждений.

### Задачи:

- Модифицировать [`knowledge_os/app/telegram_gateway.py`](knowledge_os/app/telegram_gateway.py):
    - Добавить объект `TraceContext` для сбора логов оркестрации внутри `handle_message`.
    - Сохранять в `interaction_logs.metadata` полный CoT (Chain of Thought): какой план составила Виктория, какие вопросы задавала экспертам и какие ответы получила.
- Это позволит Радару выявлять логические ошибки в рассуждениях агентов.

## 3. Слой «Agent Gym» (Synthetic Generator)

Цель: Генерация инновационных идей путем внутреннего диалога (диалектики) между экспертами.

### Задачи:

- Создать [`knowledge_os/app/synthetic_generator.py`](knowledge_os/app/synthetic_generator.py):
    - Выбирает «горячую» тему или конфликтный вопрос.
    - Инициирует дискуссию между двумя экспертами с разными ролями (например, Дмитрий (ML) и Мария (Risk)).
    - Синтезирует итог дискуссии в новый узел знаний с пометкой `source_type: synthetic`.
- Добавить запуск генератора в ночной цикл `cron`.

## Технический стек и инструменты: