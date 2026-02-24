---
name: hitl
description: Human-in-the-Loop - контроль человека для критичных операций (LangGraph, Anthropic)
category: safety
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "👤",
        "homepage": "https://langchain-ai.github.io/langgraph/",
      },
  }
---

# Human-in-the-Loop Skill

Навык на основе **Human-in-the-Loop (HITL)** от LangGraph и Anthropic. Контроль человека для критичных операций.

## Когда использовать

Используй этот навык для:

- Критичных операций (удаление, изменение важных файлов)
- Операций с высоким риском
- Решений, требующих одобрения
- Задач с неопределенностью

## Методология

HITL работает через:

1. **Risk Assessment** - Оценка риска операции
2. **Human Request** - Запрос одобрения у человека
3. **Wait for Approval** - Ожидание одобрения
4. **Execution** - Выполнение после одобрения
5. **Logging** - Логирование всех операций

## Примеры использования

```
Операция: Удаление базы данных

HITL:
1. Оценка: Высокий риск
2. Запрос: "Вы уверены, что хотите удалить БД?"
3. Ожидание: Ответ пользователя
4. Выполнение: Только после подтверждения
```

## Интеграция

Активируется через `hitl.py` для критичных операций.

## Источник

- LangGraph HITL
- Anthropic Safety
- Файл: `knowledge_os/app/hitl.py`
