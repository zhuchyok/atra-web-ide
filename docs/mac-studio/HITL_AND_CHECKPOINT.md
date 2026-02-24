# 👤 Human-in-the-Loop & Checkpoint System

**Дата:** 2026-01-25  
**Версия:** 1.0

---

## 🎯 Обзор

Два критически важных компонента для безопасности и надежности:

- **Human-in-the-Loop** - критические одобрения и feedback
- **Checkpoint & Persistence** - сохранение состояния и восстановление

---

## 👤 Human-in-the-Loop (HITL)

### Возможности

1. **Критические одобрения**
   - Автоматическое определение критичности действий
   - Запрос одобрения для опасных операций
   - Модификация результатов перед выполнением

2. **Интерактивная коррекция**
   - Возможность исправить решение агента
   - Модификация предложенного результата
   - Обратная связь для обучения

3. **Feedback loops**
   - Запись обратной связи
   - Обучение на основе фидбека
   - Статистика и рекомендации

### Критичность действий

- **CRITICAL:** delete, drop, remove, uninstall, destroy
- **HIGH:** modify_system, install, production changes
- **MEDIUM:** update_config, low confidence actions
- **LOW:** create, read, безопасные операции

### Использование

```python
from app.human_in_the_loop import get_hitl

hitl = get_hitl()

# Запрос одобрения
approval = await hitl.request_approval(
    action="delete_file",
    description="Удалить файл config.py",
    agent_name="Veronica",
    proposed_result={"file": "config.py", "action": "deleted"},
    context={"system_file": True}
)

# Одобрить
await hitl.approve(approval.request_id, approved_by="user")

# Отклонить
await hitl.reject(approval.request_id, reason="Файл нужен")

# Записать feedback
await hitl.record_feedback(
    action_id="task_123",
    agent_name="Victoria",
    feedback_type="correction",
    feedback_text="Нужно использовать другой подход",
    rating=3
)
```

### Настройка

```bash
# Включить HITL
export USE_HITL=true

# Порог confidence для запроса одобрения
export HITL_CONFIDENCE_THRESHOLD=0.7
```

---

## 💾 Checkpoint & Persistence

### Возможности

1. **Checkpoint System**
   - Создание точек восстановления
   - Восстановление после сбоев
   - Автоматическая очистка истекших checkpoint'ов

2. **State Persistence**
   - Сохранение состояния между сессиями
   - Версионирование состояний
   - Миграция между версиями

### Использование

#### Checkpoint

```python
from app.checkpoint_manager import get_checkpoint_manager

manager = await get_checkpoint_manager()

# Создать checkpoint
checkpoint = await manager.create_checkpoint(
    task_id="task_123",
    agent_name="Victoria",
    state={"step": 5, "data": {...}},
    step=5,
    progress=0.5,
    ttl_hours=24
)

# Восстановить из checkpoint
state = await manager.restore_from_checkpoint(checkpoint.checkpoint_id)

# Получить последний checkpoint для задачи
latest = await manager.get_latest_checkpoint("task_123")
```

#### State Persistence

```python
from app.state_persistence import get_state_persistence

persistence = await get_state_persistence()

# Сохранить состояние
state = await persistence.save_state(
    agent_name="Victoria",
    state_type="task",
    state_data={"goal": "...", "result": "..."},
    metadata={"priority": 9}
)

# Загрузить состояние
loaded = await persistence.load_state(state.state_id)

# Загрузить все состояния агента
all_states = await persistence.load_agent_states("Victoria", state_type="task")

# Миграция состояния
migrated = await persistence.migrate_state(
    state_id="state_123",
    migration_func=lambda old: {**old, "new_field": "value"}
)
```

---

## 🔧 Интеграция

### HITL Middleware

Автоматически проверяет критические действия в Victoria и Veronica:

```python
# В victoria_server.py и server.py уже интегрировано
# Проверка происходит автоматически при USE_HITL=true
```

### Checkpoint в Victoria Enhanced

```python
from app.checkpoint_manager import get_checkpoint_manager

manager = await get_checkpoint_manager()

# В длительных задачах создавать checkpoint'ы
for step in range(steps):
    # Выполняем шаг
    result = await execute_step(step)

    # Создаем checkpoint
    await manager.create_checkpoint(
        task_id=task_id,
        agent_name="Victoria",
        state={"step": step, "result": result},
        step=step,
        progress=step / steps
    )
```

---

## 📊 Ожидаемые улучшения

### HITL:

- **+15-20% accuracy** на критических задачах
- **Безопасность** - предотвращение опасных действий
- **Контроль качества** - человеческий надзор

### Checkpoint:

- **Надежность** - восстановление после сбоев
- **Долгие задачи** - возможность прервать и продолжить
- **Отказоустойчивость** - сохранение прогресса

---

## 🧪 Тестирование

```python
# Тест HITL
from app.human_in_the_loop import get_hitl

hitl = get_hitl()
approval = await hitl.request_approval(
    action="delete",
    description="Удалить файл",
    agent_name="Veronica",
    proposed_result={}
)
print(f"Требуется одобрение: {approval.criticality.value}")

# Тест Checkpoint
from app.checkpoint_manager import get_checkpoint_manager

manager = await get_checkpoint_manager()
checkpoint = await manager.create_checkpoint(
    task_id="test",
    agent_name="Victoria",
    state={"test": "data"},
    step=1,
    progress=0.5
)
restored = await manager.restore_from_checkpoint(checkpoint.checkpoint_id)
print(f"Восстановлено: {restored}")
```

---

## 📚 Дополнительные ресурсы

- `knowledge_os/app/human_in_the_loop.py` - HITL framework
- `knowledge_os/app/checkpoint_manager.py` - Checkpoint manager
- `knowledge_os/app/state_persistence.py` - State persistence
- `src/agents/bridge/hitl_middleware.py` - HITL middleware

---

**Обновлено:** 2026-01-25
