---
name: state-machine
description: State Machines - оркестрация и восстановление через состояния (LangGraph)
category: orchestration
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "🔄",
        "homepage": "https://langchain-ai.github.io/langgraph/",
      },
  }
---

# State Machine Skill

Навык на основе **State Machines** от LangGraph. Оркестрация задач через состояния с возможностью восстановления.

## Когда использовать

Используй этот навык для:

- Сложных многошаговых процессов
- Задач, требующих восстановления после сбоя
- Оркестрации с четкими состояниями
- Checkpoint и resume функциональности

## Методология

State Machine работает через:

1. **State Definition** - Определение состояний
2. **Transition Rules** - Правила переходов
3. **Checkpoint** - Сохранение состояния
4. **Recovery** - Восстановление после сбоя
5. **Progress Tracking** - Отслеживание прогресса

## Примеры использования

```
Задача: Развертывание приложения

State Machine:
1. State: planning → checkpoint
2. State: building → checkpoint
3. State: testing → checkpoint
4. State: deploying → checkpoint
5. Если сбой на шаге 3 → восстановление из checkpoint
```

## Интеграция

Активируется через `state_machine.py` для оркестрации.

## Источник

- LangGraph State Machines
- Файл: `knowledge_os/app/state_machine.py`
