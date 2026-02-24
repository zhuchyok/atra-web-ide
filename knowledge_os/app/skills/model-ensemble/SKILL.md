---
name: model-ensemble
description: Model Ensemble - использование нескольких моделей для критичных задач
category: quality
version: 1.0.0
author: ATRA Corporation
metadata: { "clawdbot": { "requires": {}, "emoji": "🎯" } }
---

# Model Ensemble Skill

Навык на основе **Model Ensemble** методов. Использование нескольких моделей для критичных задач обеспечивает +10-25% улучшение.

## Когда использовать

Используй этот навык для:

- Критичных решений
- Задач, требующих высокой точности
- Важных архитектурных решений
- Задач с высоким риском ошибки

## Методология

Model Ensemble работает через:

1. **Multiple Models** - Использование нескольких моделей
2. **Parallel Execution** - Параллельное выполнение
3. **Voting** - Голосование или взвешенное голосование
4. **Consensus** - Построение консенсуса
5. **Final Decision** - Финальное решение

## Примеры использования

```
Критичная задача: Выбор архитектуры для production системы

Model Ensemble:
- Model 1 (qwen2.5-coder): Микросервисы
- Model 2 (deepseek-r1): Модульный монолит
- Model 3 (llama3.1): Гибридный подход
→ Консенсус: Гибридный подход (2 из 3)
```

## Интеграция

Активируется через `model_enhancer.py` для критичных задач.

## Источник

- Ensemble methods research
- Файл: `knowledge_os/app/model_enhancer.py`
