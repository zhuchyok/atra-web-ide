---
name: extended-thinking
description: Extended Thinking Mode - глубокое рассуждение для сложных проблем
category: reasoning
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "💭",
        "homepage": "https://www.anthropic.com/research/extended-thinking",
      },
  }
---

# Extended Thinking Skill

Навык на основе **Extended Thinking Mode** от Anthropic Claude. Обеспечивает +20-30% улучшение на reasoning задачи.

## Когда использовать

Используй этот навык для:

- Сложных аналитических задач
- Задач, требующих глубокого рассуждения
- Проблем без очевидного решения
- Задач, где нужно рассмотреть множество вариантов

## Методология

Extended Thinking работает через:

1. **Deep Analysis** - Глубокий анализ проблемы
2. **Multi-Perspective** - Рассмотрение с разных точек зрения
3. **Chain of Thought** - Цепочка рассуждений
4. **Validation** - Проверка логики и выводов

## Примеры использования

```
Пользователь: "Почему этот код работает медленно?"

Extended Thinking:
1. Анализ структуры кода
2. Поиск узких мест (bottlenecks)
3. Рассмотрение альтернативных подходов
4. Оценка сложности алгоритмов
5. Рекомендации по оптимизации
```

## Интеграция

Активируется автоматически через `extended_thinking.py` для сложных reasoning задач.

## Источник

- Anthropic Claude Extended Thinking
- Файл: `knowledge_os/app/extended_thinking.py`
