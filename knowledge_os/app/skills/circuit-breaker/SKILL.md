---
name: circuit-breaker
description: Circuit Breaker - защита от каскадных сбоев (Singularity 6.0)
category: reliability
version: 1.0.0
author: ATRA Corporation
metadata: {"clawdbot": {"requires": {}, "emoji": "⚡"}}
---

# Circuit Breaker Skill

Навык на основе **Circuit Breaker** от Singularity 6.0. Защита от каскадных сбоев и обеспечение отказоустойчивости.

## Когда использовать

Используй этот навык для:
- Защиты от каскадных сбоев
- Отказоустойчивости системы
- Предотвращения перегрузки
- Быстрого восстановления

## Методология

Circuit Breaker работает через:
1. **Monitoring** - Мониторинг ошибок
2. **Threshold** - Порог ошибок
3. **Open Circuit** - Открытие цепи при превышении порога
4. **Fast Fail** - Быстрый отказ вместо ожидания
5. **Recovery** - Автоматическое восстановление

## Примеры использования

```
Сценарий: MLX API Server недоступен

Circuit Breaker:
1. Обнаружение: 5 ошибок подряд
2. Действие: Открытие цепи (circuit open)
3. Поведение: Быстрый fallback на Ollama
4. Мониторинг: Периодическая проверка восстановления
5. Восстановление: Автоматическое закрытие цепи
```

## Интеграция

Активируется через `circuit_breaker.py` для отказоустойчивости.

## Источник

- Singularity 6.0
- Файл: `knowledge_os/app/circuit_breaker.py`