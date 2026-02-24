---
name: disaster-recovery
description: Disaster Recovery - автоматическое восстановление после сбоев (Singularity 6.0)
category: reliability
version: 1.0.0
author: ATRA Corporation
metadata: { "clawdbot": { "requires": {}, "emoji": "🔄" } }
---

# Disaster Recovery Skill

Навык на основе **Disaster Recovery** от Singularity 6.0. Автоматическое восстановление системы после сбоев.

## Когда использовать

Используй этот навык для:

- Автоматического восстановления после сбоев
- Сохранения состояния
- Восстановления из checkpoint
- Непрерывной работы системы

## Методология

Disaster Recovery работает через:

1. **Checkpointing** - Регулярное сохранение состояния
2. **State Backup** - Резервное копирование состояния
3. **Failure Detection** - Обнаружение сбоев
4. **Recovery** - Восстановление из checkpoint
5. **Validation** - Проверка восстановления

## Примеры использования

```
Сценарий: Сбой во время выполнения задачи

Disaster Recovery:
1. Checkpoint: Сохранение состояния каждые 10 шагов
2. Сбой: Обнаружение ошибки
3. Восстановление: Загрузка последнего checkpoint
4. Продолжение: Возобновление с сохраненной точки
5. Завершение: Успешное выполнение задачи
```

## Интеграция

Активируется через `disaster_recovery.py` для автоматического восстановления.

## Источник

- Singularity 6.0
- Файл: `knowledge_os/app/disaster_recovery.py`
