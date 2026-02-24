---
name: collective-memory
description: Collective Memory - использование накопленных знаний команды (Stigmergy pattern)
category: knowledge
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "🧬",
        "homepage": "https://en.wikipedia.org/wiki/Stigmergy",
      },
  }
---

# Collective Memory Skill

Навык на основе **Collective Memory** (Stigmergy pattern). Обеспечивает +68.7% улучшение performance через использование накопленных знаний.

## Когда использовать

Используй этот навык для:

- Использования знаний из предыдущих задач
- Поиска решений в базе знаний
- Обучения на опыте команды
- Избежания повторения ошибок

## Методология

Collective Memory работает через:

1. **Knowledge Retrieval** - Поиск релевантных знаний
2. **Pattern Matching** - Сопоставление с похожими задачами
3. **Solution Adaptation** - Адаптация решений
4. **Knowledge Update** - Обновление базы знаний

## Примеры использования

```
Пользователь: "Создай систему авторизации"

Collective Memory:
1. Поиск в базе знаний: "Как создавали авторизацию раньше?"
2. Найдено: 3 похожих решения
3. Адаптация: Использование лучших практик
4. Обновление: Сохранение нового опыта
```

## Интеграция

Активируется через `collective_memory.py` и Knowledge OS базу данных.

## Источник

- Stigmergy research
- Collective Intelligence
- Файл: `knowledge_os/app/collective_memory.py`
