---
name: recap-framework
description: ReCAP Framework - Reasoning, Context, Action, Planning (Meta pattern)
category: reasoning
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "📋",
        "homepage": "https://ai.meta.com/research/publications/recap/",
      },
  }
---

# ReCAP Framework Skill

Навык на основе **ReCAP Framework** от Meta. Обеспечивает +32% улучшение на multi-step reasoning.

## Когда использовать

Используй этот навык для:

- Многошаговых reasoning задач
- Задач, требующих контекста
- Сложных последовательностей действий
- Задач с зависимостями между шагами

## Методология

ReCAP Framework работает через 4 фазы:

1. **Reasoning** - Рассуждение о задаче
2. **Context** - Сбор и анализ контекста
3. **Action** - Планирование действий
4. **Planning** - Детальное планирование выполнения

## Примеры использования

```
Пользователь: "Создай REST API для управления пользователями"

ReCAP:
1. Reasoning: Нужен API с CRUD операциями
2. Context: Проверка существующих файлов, структуры проекта
3. Action: Создание endpoints, моделей, валидации
4. Planning: Последовательность создания файлов
```

## Интеграция

Активируется через `recap_framework.py` для multi-step reasoning задач.

## Источник

- Meta ReCAP: Reasoning, Context, Action, Planning
- Файл: `knowledge_os/app/recap_framework.py`
