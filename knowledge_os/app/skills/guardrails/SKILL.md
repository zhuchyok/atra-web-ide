---
name: guardrails
description: Guardrails - работа в рамках ограничений и правил (OpenAI Agent Guide)
category: safety
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "🛡️",
        "homepage": "https://platform.openai.com/docs/guides/agents",
      },
  }
---

# Guardrails Skill

Навык на основе **Guardrails** от OpenAI Agent Guide. Обеспечивает работу в рамках ограничений и правил безопасности.

## Когда использовать

Используй этот навык для:

- Проверки безопасности действий
- Валидации перед выполнением
- Соблюдения правил проекта
- Предотвращения опасных операций

## Методология

Guardrails работает через:

1. **Rule Definition** - Определение правил
2. **Pre-Execution Check** - Проверка перед выполнением
3. **Validation** - Валидация действий
4. **Blocking** - Блокировка опасных операций
5. **Logging** - Логирование нарушений

## Примеры использования

```
Действие: Удаление системных файлов

Guardrails:
1. Проверка: Системные файлы в списке запрещенных
2. Валидация: Действие заблокировано
3. Логирование: Попытка удаления системного файла
4. Уведомление: Предупреждение пользователю
```

## Интеграция

Активируется через `guardrails.py` для безопасности.

## Источник

- OpenAI Agent Guide
- Файл: `knowledge_os/app/guardrails.py`
