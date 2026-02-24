---
name: observability
description: Observability - полная диагностика системы через OpenTelemetry (Microsoft AutoGen)
category: monitoring
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": { "bins": ["python"] },
        "emoji": "📊",
        "homepage": "https://opentelemetry.io/",
      },
  }
---

# Observability Skill

Навык на основе **Observability** через OpenTelemetry от Microsoft AutoGen. Полная диагностика и мониторинг системы.

## Когда использовать

Используй этот навык для:

- Диагностики проблем
- Мониторинга производительности
- Отслеживания выполнения задач
- Анализа метрик
- Debugging

## Методология

Observability работает через:

1. **Tracing** - Трассировка выполнения
2. **Metrics** - Сбор метрик
3. **Logging** - Структурированное логирование
4. **Analysis** - Анализ данных
5. **Visualization** - Визуализация

## Примеры использования

```
Проблема: Медленное выполнение задачи

Observability:
1. Трассировка: Где задержка?
2. Метрики: Время выполнения каждого шага
3. Анализ: Обнаружение bottleneck
4. Решение: Оптимизация медленного шага
```

## Интеграция

Активируется через `observability.py` для диагностики и мониторинга.

## Источник

- Microsoft AutoGen Observability
- OpenTelemetry
- Файл: `knowledge_os/app/observability.py`
