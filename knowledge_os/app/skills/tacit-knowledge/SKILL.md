---
name: tacit-knowledge
description: Tacit Knowledge Extractor - извлечение неявных знаний о стиле пользователя (Singularity 9.0)
category: personalization
version: 1.0.0
author: ATRA Corporation
metadata: { "clawdbot": { "requires": {}, "emoji": "🎨" } }
---

# Tacit Knowledge Skill

Навык на основе **Tacit Knowledge Extractor** от Singularity 9.0. Извлечение неявных знаний о стиле пользователя обеспечивает style_similarity > 0.85.

## Когда использовать

Используй этот навык для:

- Понимания стиля кода пользователя
- Адаптации под предпочтения
- Генерации кода в стиле пользователя
- Персонализации ответов

## Методология

Tacit Knowledge работает через:

1. **Code Analysis** - Анализ существующего кода пользователя
2. **Pattern Extraction** - Извлечение паттернов стиля
3. **Style Learning** - Обучение на стиле
4. **Application** - Применение стиля в новых задачах
5. **Validation** - Проверка соответствия стилю

## Примеры использования

```
Анализ кода пользователя:

Tacit Knowledge:
1. Паттерн: Использование type hints везде
2. Паттерн: Документация в формате Google style
3. Паттерн: Использование async/await
4. Применение: Генерация нового кода в том же стиле
5. Результат: style_similarity = 0.92
```

## Интеграция

Активируется через `tacit_knowledge_miner.py` и `codebase_understanding.py` для персонализации.

## Источник

- Singularity 9.0
- Файлы: `knowledge_os/app/tacit_knowledge_miner.py`, `codebase_understanding.py`
