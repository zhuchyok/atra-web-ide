---
name: self-learning
description: Self-Learning Agents - автоматическое обучение и адаптация (Google DeepMind SIMA 2)
category: learning
version: 1.0.0
author: ATRA Corporation
metadata: { "clawdbot": { "requires": {}, "emoji": "🎓" } }
---

# Self-Learning Skill

Навык на основе **Self-Learning Agents** от Google DeepMind SIMA 2. Автоматическое обучение и адаптация на основе опыта.

## Когда использовать

Используй этот навык для:

- Автоматического улучшения на основе опыта
- Адаптации к новым задачам
- Обучения на ошибках
- Непрерывного улучшения качества

## Методология

Self-Learning работает через:

1. **Experience Collection** - Сбор опыта выполнения задач
2. **Pattern Recognition** - Распознавание паттернов успеха/неудачи
3. **Knowledge Update** - Обновление базы знаний
4. **Strategy Adaptation** - Адаптация стратегий
5. **Performance Improvement** - Улучшение производительности

## Примеры использования

```
После выполнения 10 задач по созданию API:

Self-Learning:
1. Анализ: Какие подходы работали лучше?
2. Паттерн: Использование FastAPI + Pydantic = успех
3. Обновление: Добавление в базу знаний
4. Адаптация: Автоматический выбор FastAPI для новых API
```

## Интеграция

Активируется через `self_learning_agent.py` для непрерывного обучения.

## Источник

- Google DeepMind SIMA 2
- Файл: `knowledge_os/app/self_learning_agent.py`
