---
name: streaming
description: Streaming - потоковая генерация ответов для улучшения UX (Singularity 5.0)
category: ux
version: 1.0.0
author: ATRA Corporation
metadata: { "clawdbot": { "requires": {}, "emoji": "🌊" } }
---

# Streaming Skill

Навык на основе **Streaming** от Singularity 5.0. Потоковая генерация ответов обеспечивает +50-100% улучшение воспринимаемой скорости.

## Когда использовать

Используй этот навык для:

- Длинных ответов
- Улучшения UX
- Интерактивных задач
- Реального времени

## Методология

Streaming работает через:

1. **Chunk Generation** - Генерация по частям
2. **Immediate Delivery** - Немедленная доставка
3. **Progressive Display** - Постепенное отображение
4. **User Feedback** - Обратная связь пользователя
5. **Adaptation** - Адаптация под обратную связь

## Примеры использования

```
Длинная задача: Генерация кода (1000 строк)

Streaming:
1. Chunk 1 (100 строк) → отправка
2. Chunk 2 (100 строк) → отправка
3. ...
→ Пользователь видит прогресс в реальном времени
```

## Интеграция

Активируется через `streaming_worker.py` для улучшения UX.

## Источник

- Singularity 5.0
- Файл: `knowledge_os/app/streaming_worker.py`
