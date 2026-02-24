---
name: self-correction
description: Self-Correction - автоматическое исправление ошибок (OpenAI o1 pattern)
category: quality
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "🔧",
        "homepage": "https://openai.com/research/o1",
      },
  }
---

# Self-Correction Skill

Навык на основе **Self-Correction** от OpenAI o1. Автоматически исправляет ошибки в коде и решениях.

## Когда использовать

Используй этот навык для:

- Автоматической проверки и исправления кода
- Валидации решений перед выполнением
- Исправления ошибок выполнения
- Улучшения качества ответов

## Методология

Self-Correction работает через:

1. **Execution** - Выполнение кода/решения
2. **Error Detection** - Обнаружение ошибок
3. **Analysis** - Анализ причины ошибки
4. **Correction** - Исправление ошибки
5. **Validation** - Проверка исправления

## Примеры использования

````
Код с ошибкой:
```python
def add(a, b):
    return a + c  # Ошибка: 'c' не определено
````

Self-Correction:

1. Обнаружение ошибки: NameError: name 'c' is not defined
2. Анализ: Должно быть 'b' вместо 'c'
3. Исправление: return a + b
4. Валидация: Код работает корректно

```

## Интеграция

Активируется автоматически через `self_correction.py` при обнаружении ошибок.

## Источник

- OpenAI o1: Reasoning, Fast and Slow
- Файл: `knowledge_os/app/self_correction.py`
```
