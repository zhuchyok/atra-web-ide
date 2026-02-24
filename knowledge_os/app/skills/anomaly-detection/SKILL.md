---
name: anomaly-detection
description: Anomaly Detection - обнаружение аномалий и атак (Singularity 7.5)
category: security
version: 1.0.0
author: ATRA Corporation
metadata: { "clawdbot": { "requires": {}, "emoji": "🚨" } }
---

# Anomaly Detection Skill

Навык на основе **Anomaly Detection** от Singularity 7.5. Обнаружение аномалий и защита от атак.

## Когда использовать

Используй этот навык для:

- Обнаружения аномалий в поведении
- Защиты от атак
- Обнаружения подозрительной активности
- Мониторинга безопасности

## Методология

Anomaly Detection работает через:

1. **Baseline** - Установление базовой линии поведения
2. **Monitoring** - Мониторинг активности
3. **Pattern Analysis** - Анализ паттернов
4. **Anomaly Detection** - Обнаружение отклонений
5. **Alerting** - Уведомления о подозрительной активности

## Примеры использования

```
Сценарий: Подозрительный запрос

Anomaly Detection:
1. Анализ: Запрос не соответствует обычным паттернам
2. Обнаружение: Попытка инъекции кода
3. Действие: Блокировка запроса
4. Уведомление: Алерт в Telegram
5. Логирование: Сохранение для анализа
```

## Интеграция

Активируется через `anomaly_detector.py` и `threat_detector.py` для безопасности.

## Источник

- Singularity 7.5
- Файлы: `knowledge_os/app/anomaly_detector.py`, `threat_detector.py`
