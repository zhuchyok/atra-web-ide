# Victoria - Поддержка всех моделей из PLAN.md

**Дата:** 2026-01-26  
**Статус:** ✅ Реализовано

## 🎯 Цель

Настроить Victoria для работы со всеми моделями из PLAN.md с автоматическим выбором оптимальной модели на основе категории задачи.

## 📋 Модели из PLAN.md

| Модель                        | Размер | Назначение                                  | Автовыбор                   |
| ----------------------------- | ------ | ------------------------------------------- | --------------------------- |
| command-r-plus:104b           | ~65GB  | Максимальная мощность, RAG, мультиязычность | ✅ complex, enterprise      |
| deepseek-r1-distill-llama:70b | ~40GB  | Reasoning, планирование (distilled)         | ✅ reasoning                |
| llama3.3:70b                  | ~40GB  | Максимальное качество, общие задачи         | ✅ complex                  |
| qwen2.5-coder:32b             | ~20GB  | Качественный код, рефакторинг               | ✅ coding (high quality)    |
| phi3.5:3.8b                   | ~2.5GB | Быстрые задачи, общие                       | ✅ fast, general            |
| phi3:mini-4k                  | ~2GB   | Быстрые ответы, легкие задачи               | ✅ fast (lightweight)       |
| qwen2.5:3b                    | ~2GB   | Быстрые ответы, общие задачи                | ✅ fast, default            |
| tinyllama:1.1b-chat           | ~700MB | Очень быстрые ответы                        | ✅ fast (ultra-lightweight) |

## ✅ Реализовано

### 1. Victoria Enhanced - Автоматический выбор модели

**Файл:** `knowledge_os/app/victoria_enhanced.py`

- ✅ Добавлен метод `_get_model_for_category_async()` - выбирает модель на основе категории задачи
- ✅ Приоритеты моделей по категориям из PLAN.md:
  - **complex/enterprise**: command-r-plus:104b → llama3.3:70b → deepseek-r1-distill-llama:70b
  - **reasoning**: deepseek-r1-distill-llama:70b → llama3.3:70b → qwen2.5-coder:32b
  - **coding**: qwen2.5-coder:32b → phi3.5:3.8b → qwen2.5:3b
  - **fast**: phi3.5:3.8b → phi3:mini-4k → qwen2.5:3b → tinyllama:1.1b-chat
  - **planning**: deepseek-r1-distill-llama:70b → llama3.3:70b → qwen2.5-coder:32b
  - **execution**: qwen2.5-coder:32b → phi3.5:3.8b → qwen2.5:3b
  - **general**: qwen2.5-coder:32b → phi3.5:3.8b → qwen2.5:3b → tinyllama:1.1b-chat

- ✅ Extended Thinking использует оптимальную модель для reasoning задач
- ✅ Swarm Intelligence использует оптимальную модель для complex задач
- ✅ Consensus использует оптимальную модель для complex задач

### 2. Extended Thinking - Fallback на все модели

**Файл:** `knowledge_os/app/extended_thinking.py`

- ✅ Добавлен fallback на все модели из списка приоритетов
- ✅ Если основная модель недоступна (404), пробует:
  1. deepseek-r1-distill-llama:70b
  2. llama3.3:70b
  3. qwen2.5-coder:32b
  4. phi3.5:3.8b
  5. qwen2.5:3b
  6. phi3:mini-4k
  7. tinyllama:1.1b-chat

### 3. Victoria Agent - Динамический выбор модели

**Файл:** `src/agents/bridge/victoria_server.py`

- ✅ Добавлен метод `_select_model_for_task()` - выбирает модель на основе категории задачи
- ✅ Интеграция с `model_selector` для проверки доступности моделей
- ✅ Автоматическое обновление модели executor при выполнении задачи

### 4. Категоризация задач

Victoria автоматически определяет категорию задачи:

- **coding**: "код", "программируй", "напиши код"
- **reasoning**: "реши", "рассчитай", "reasoning", "логика"
- **complex**: "сложн", "комплекс", "complex", "enterprise"
- **fast**: простые задачи (≤5 слов)
- **general**: остальные задачи

## 🔧 Как это работает

### Процесс выбора модели:

1. **Определение категории задачи** → `_categorize_task(goal)`
2. **Выбор приоритетов моделей** → список моделей для категории
3. **Проверка доступности** → `model_selector.select_available_model()`
4. **Использование первой доступной** → fallback на следующую если недоступна
5. **Обновление компонентов** → Extended Thinking, Swarm, Consensus используют выбранную модель

### Пример:

```python
# Задача: "Реши сложную математическую задачу"
# 1. Категория: "reasoning"
# 2. Приоритеты: ["deepseek-r1-distill-llama:70b", "llama3.3:70b", ...]
# 3. Проверка: deepseek-r1-distill-llama:70b недоступна → пробуем llama3.3:70b
# 4. Результат: используется llama3.3:70b для Extended Thinking
```

## 📊 Текущий статус

- ✅ Victoria Enhanced поддерживает все модели из PLAN.md
- ✅ Extended Thinking с fallback на все модели
- ✅ Victoria Agent с динамическим выбором модели
- ✅ Автоматическая категоризация задач
- ✅ Проверка доступности моделей с fallback

## 🚀 Использование

Victoria автоматически выберет оптимальную модель для каждой задачи:

- **Сложные задачи** → command-r-plus:104b или llama3.3:70b
- **Reasoning задачи** → deepseek-r1-distill-llama:70b или llama3.3:70b
- **Coding задачи** → qwen2.5-coder:32b
- **Простые задачи** → phi3.5:3.8b или tinyllama:1.1b-chat

Если нужная модель недоступна, автоматически используется следующая из списка приоритетов.

---

**Готово!** Victoria теперь работает со всеми моделями из PLAN.md! 🎉
