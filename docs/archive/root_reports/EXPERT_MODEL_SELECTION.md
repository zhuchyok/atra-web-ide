# 🎯 Выбор моделей экспертами

**Дата:** 2026-01-26  
**Статус:** ✅ **РЕАЛИЗОВАНО**

---

## 🏗️ ГИБРИДНЫЙ ПОДХОД

### Варианты выбора моделей:

1. **Эксперт сам выбирает** (`expert_choice`)
   - Эксперт имеет достаточно знаний
   - Может выбрать оптимальную модель для задачи
   - Получает рекомендации, но решает сам

2. **Следовать рекомендациям** (`recommended`)
   - Вероника рекомендует конкретные модели
   - Эксперт следует рекомендациям
   - Для сложных задач или когда эксперт не уверен

3. **Автоматический выбор** (`auto`)
   - Система сама выбирает модель
   - На основе категории задачи
   - Для простых задач

---

## 📊 ПРОЦЕСС

### 1. Victoria создает промпт с рекомендациями моделей

```json
{
  "subtasks": [
    {
      "subtask": "Создать API endpoint",
      "department": "Backend",
      "expert_role": "Backend Developer",
      "recommended_models": ["qwen2.5-coder:32b", "phi3.5:3.8b"],
      "model_selection": "expert_choice"
    }
  ]
}
```

### 2. Вероника передает рекомендации эксперту

```
ПОДЗАДАЧА: Создать API endpoint
- Отдел: Backend
- Эксперт: Backend Developer
- РЕКОМЕНДУЕМЫЕ МОДЕЛИ: qwen2.5-coder:32b, phi3.5:3.8b (можешь выбрать сам или использовать рекомендации)
```

### 3. Эксперт выбирает модель

**Вариант A: Эксперт уверен (expert_choice)**

```python
async def expert_execute_task(task, recommended_models):
    # Эксперт анализирует задачу
    if expert_has_knowledge(task):
        # Выбирает свою модель
        selected_model = expert_select_model(task)
    else:
        # Использует рекомендации
        selected_model = recommended_models[0]

    result = await execute_with_model(task, selected_model)
```

**Вариант B: Следовать рекомендациям (recommended)**

```python
async def expert_execute_task(task, recommended_models):
    # Использует первую рекомендованную модель
    selected_model = recommended_models[0]
    result = await execute_with_model(task, selected_model)
```

**Вариант C: Автоматический выбор (auto)**

```python
async def expert_execute_task(task):
    # Система выбирает модель
    selected_model = await auto_select_model(task.category)
    result = await execute_with_model(task, selected_model)
```

---

## ✅ ПРЕИМУЩЕСТВА

1. **Гибкость:**
   - Эксперты с опытом могут выбрать оптимальную модель
   - Новички следуют рекомендациям

2. **Качество:**
   - Вероника рекомендует модели на основе анализа задачи
   - Эксперт может скорректировать выбор

3. **Автономия:**
   - Эксперт сам решает, следовать рекомендациям или выбрать свою модель

---

## 🎯 РЕКОМЕНДАЦИИ ПО МОДЕЛЯМ

### Victoria анализирует задачу и рекомендует:

- **Coding задачи** → `qwen2.5-coder:32b`, `phi3.5:3.8b`
- **Reasoning задачи** → `deepseek-r1-distill-llama:70b`
- **Быстрые задачи** → `phi3:mini-4k`, `qwen2.5:3b`
- **Сложные задачи** → `llama3.3:70b`, `command-r-plus:104b`

---

**Статус:** ✅ **РЕАЛИЗОВАНО - ГИБРИДНЫЙ ПОДХОД**
