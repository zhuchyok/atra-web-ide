---
name: consensus-agent
description: Consensus Agent - согласование мнений нескольких экспертов
category: collaboration
version: 1.0.0
author: ATRA Corporation
metadata: { "clawdbot": { "requires": {}, "emoji": "🤝" } }
---

# Consensus Agent Skill

Навык на основе **Consensus Agent** - согласование мнений нескольких экспертов для критичных решений.

## Когда использовать

Используй этот навык для:

- Критичных решений, требующих консенсуса
- Задач с неоднозначными ответами
- Важных архитектурных решений
- Задач, где нужна валидация от нескольких экспертов

## Методология

Consensus Agent работает через:

1. **Expert Consultation** - Консультация с несколькими экспертами
2. **Opinion Collection** - Сбор мнений
3. **Conflict Resolution** - Разрешение конфликтов
4. **Consensus Building** - Построение консенсуса
5. **Final Decision** - Финальное решение

## Примеры использования

```
Пользователь: "Какую архитектуру выбрать для масштабируемого API?"

Consensus:
- Expert 1: Микросервисы (масштабируемость)
- Expert 2: Модульный монолит (простота)
- Expert 3: Гибридный подход (баланс)
→ Консенсус: Гибридный подход для начала, миграция к микросервисам
```

## Интеграция

Активируется через `consensus_agent.py` для критичных решений.

## Источник

- Distributed Consensus research
- Файл: `knowledge_os/app/consensus_agent.py`
