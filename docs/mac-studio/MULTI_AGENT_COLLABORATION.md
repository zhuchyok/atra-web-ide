# 🤝 Multi-Agent Collaboration Framework

**Дата:** 2026-01-25  
**Версия:** 1.0

---

## 🎯 Обзор

Фреймворк для координации и коллаборации между Victoria, Veronica и экспертами. Автоматическое делегирование задач, координация сложных задач, разрешение конфликтов.

---

## 🚀 Возможности

### 1. Автоматическое делегирование

**Умный выбор агента** на основе:
- Типа задачи (планирование, выполнение, файлы, исследования)
- Способностей агентов
- Текущей загрузки
- Приоритета задачи

**Пример:**
```python
from app.task_delegation import get_task_delegator

delegator = get_task_delegator()
task = await delegator.delegate_smart("Спланируй разработку проекта")
# Автоматически выберет Victoria для планирования
```

### 2. Координация сложных задач

**Автоматическая координация** между агентами:
1. Victoria планирует задачу
2. Veronica выполняет план
3. Victoria проверяет результат

**Пример:**
```python
from app.multi_agent_collaboration import get_collaboration

collab = get_collaboration()
result = await collab.coordinate_complex_task(
    "Разработай и протестируй REST API"
)
```

### 3. Разрешение конфликтов

**Автоматическое разрешение** разногласий между агентами через консенсус.

**Пример:**
```python
result = await collab.resolve_conflict(
    "Выбор технологии",
    {
        "Victoria": "Python + FastAPI",
        "Veronica": "Node.js + Express"
    }
)
```

---

## 📋 Классификация задач

### TaskType

- **PLANNING** → Victoria
- **EXECUTION** → Veronica
- **FILE_OPERATION** → Veronica
- **RESEARCH** → Veronica
- **COORDINATION** → Victoria
- **COMPLEX** → Требует координации
- **REASONING** → Оба могут

---

## 🔧 Использование

### Простое делегирование

```python
from app.multi_agent_collaboration import MultiAgentCollaboration

collab = MultiAgentCollaboration()

# Делегировать задачу
task = await collab.delegate_task(
    goal="Прочитай файл src/main.py",
    preferred_agent="Veronica",
    priority=7
)

# Выполнить задачу
result = await collab.execute_task(task)
```

### Умное делегирование

```python
from app.task_delegation import TaskDelegator

delegator = TaskDelegator()

# Автоматический выбор агента
task = await delegator.delegate_smart(
    goal="Спланируй архитектуру системы",
    priority=9
)

# Выполнить
result = await collab.execute_task(task)
```

### Координация сложной задачи

```python
result = await collab.coordinate_complex_task(
    goal="Разработай веб-приложение с нуля"
)

print(f"Успех: {result.success}")
print(f"Участники: {result.participants}")
print(f"Результат: {result.result}")
```

---

## 📊 Профили агентов

### Victoria
- **Способности:** Planning, Reasoning, Coordination, Code Analysis
- **Эффективность:** Planning (95%), Coordination (98%)
- **Макс. задач:** 10

### Veronica
- **Способности:** Execution, File Operations, Research, System Admin
- **Эффективность:** File Operations (98%), Execution (95%)
- **Макс. задач:** 8

---

## 🎯 Интеграция с Victoria Enhanced

Multi-Agent Collaboration может использоваться внутри Victoria Enhanced для координации сложных задач:

```python
from app.victoria_enhanced import VictoriaEnhanced
from app.multi_agent_collaboration import get_collaboration

enhanced = VictoriaEnhanced()
collab = get_collaboration()

# Для сложных задач используем координацию
if task_complexity == "high":
    result = await collab.coordinate_complex_task(goal)
else:
    result = await enhanced.solve(goal)
```

---

## 📈 Ожидаемые улучшения

- **+40-60% эффективности** на сложных задачах
- **Автоматическое распределение** нагрузки
- **Лучшая координация** между агентами
- **Разрешение конфликтов** автоматически

---

## 🧪 Тестирование

```bash
python scripts/test_collaboration.py
```

**Тесты:**
- ✅ Простое делегирование
- ✅ Координация сложных задач
- ✅ Разрешение конфликтов

---

## 📚 Дополнительные ресурсы

- `knowledge_os/app/multi_agent_collaboration.py` - основной фреймворк
- `knowledge_os/app/task_delegation.py` - умное делегирование
- `scripts/test_collaboration.py` - тесты

---

**Обновлено:** 2026-01-25
