---
name: hierarchical-orchestration
description: Hierarchical Orchestration - иерархическая координация сложных задач
category: orchestration
version: 1.0.0
author: ATRA Corporation
metadata: { "clawdbot": { "requires": {}, "emoji": "🏗️" } }
---

# Hierarchical Orchestration Skill

Навык на основе **Hierarchical Orchestration** от Meta и Microsoft. Координирует сложные задачи через иерархию агентов.

## Когда использовать

Используй этот навык для:

- Очень сложных задач с множеством подзадач
- Задач, требующих координации нескольких агентов
- Проектов с зависимостями
- Масштабных изменений

## Методология

Hierarchical Orchestration работает через:

1. **Task Decomposition** - Разбиение на подзадачи
2. **Hierarchy Creation** - Создание иерархии агентов
3. **Dependency Resolution** - Разрешение зависимостей
4. **Parallel Execution** - Параллельное выполнение где возможно
5. **Integration** - Интеграция результатов

## Примеры использования

```
Пользователь: "Рефакторинг всей кодовой базы"

Hierarchical Orchestration:
├─ Level 1: Главный координатор
│  ├─ Level 2: Модуль A (агент 1)
│  ├─ Level 2: Модуль B (агент 2)
│  └─ Level 2: Модуль C (агент 3)
└─ Integration: Объединение результатов
```

## Интеграция

Активируется через `hierarchical_orchestration.py` для очень сложных задач.

## Источник

- Meta hierarchical systems
- Microsoft AutoGen v0.4
- Файл: `knowledge_os/app/hierarchical_orchestration.py`
