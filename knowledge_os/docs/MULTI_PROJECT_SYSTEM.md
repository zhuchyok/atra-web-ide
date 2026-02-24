# 🌐 СИСТЕМА МУЛЬТИПРОЕКТНОСТИ ДЛЯ АГЕНТОВ-СОТРУДНИКОВ

**Дата:** 2025-01-XX  
**Статус:** ✅ **РЕАЛИЗОВАНО**

---

## 🎯 ОПИСАНИЕ

Система позволяет агентам-сотрудникам работать с несколькими проектами одновременно:

- Переключение между проектами
- Изоляция данных между проектами
- Общие и проект-специфичные знания
- Управление доступом агентов к проектам

---

## 📁 СТРУКТУРА

### **Модули:**

1. **`observability/project_manager.py`**
   - Создание и управление проектами
   - Назначение агентов на проекты
   - Переключение между проектами

2. **`observability/project_context.py`**
   - Контекстные менеджеры для работы с проектами
   - Изоляция данных

3. **`observability/multi_project_knowledge.py`**
   - Глобальные знания (для всех проектов)
   - Проект-специфичные знания
   - Обмен знаниями между проектами

4. **`observability/project_isolation.py`**
   - Изоляция данных между проектами
   - Отдельные директории для каждого проекта

5. **`observability/multi_project_integration.py`**
   - Интеграция мультипроектности во все системы

6. **`observability/project_aware_systems.py`**
   - Адаптация всех систем для работы с проектами

---

## 🚀 ИСПОЛЬЗОВАНИЕ

### **1. Создание проекта:**

```bash
python scripts/manage_projects.py create \
    --name "ATRA Trading" \
    --description "Алгоритмическая торговля на крипторынке" \
    --capabilities ml analysis trading
```

### **2. Назначение агента на проект:**

```bash
python scripts/manage_projects.py assign \
    --project-id project_atra_trading_1234567890 \
    --agent signal_live \
    --role "Data Analyst" \
    --capabilities ml analysis signals
```

### **3. Переключение между проектами:**

```bash
python scripts/manage_projects.py switch \
    --project-id project_atra_trading_1234567890
```

### **4. Список проектов:**

```bash
# Все проекты
python scripts/manage_projects.py list

# Проекты конкретного агента
python scripts/manage_projects.py list --agent signal_live
```

### **5. Статус проекта:**

```bash
python scripts/manage_projects.py status --project-id project_atra_trading_1234567890
```

---

## 💻 ИСПОЛЬЗОВАНИЕ В КОДЕ

### **Работа в контексте проекта:**

```python
from observability.project_context import project_context

with project_context("project_atra_trading_1234567890"):
    # Все операции выполняются в контексте проекта
    from observability.mentorship import get_mentorship_system
    system = get_mentorship_system()
    system.update_agent_rating("signal_live", "Data Analyst", success=True)
```

### **Декоратор для проекта:**

```python
from observability.project_context import with_project

@with_project("project_atra_trading_1234567890")
def generate_signal():
    # Код генерации сигнала
    pass
```

### **Обработка активности для проекта:**

```python
from observability.multi_project_integration import get_multi_project_integration

integration = get_multi_project_integration()
integration.process_agent_activity_for_project(
    project_id="project_atra_trading_1234567890",
    agent="signal_live",
    role="Data Analyst",
    activity_type="signal_generated",
    success=True,
    metrics={"win_rate": 0.75},
)
```

---

## 📊 СТРУКТУРА ДАННЫХ

### **Директории проектов:**

```
projects/
├── project_atra_trading_1234567890/
│   ├── retrospectives/
│   ├── guidance/
│   ├── lessons/
│   ├── metrics/
│   ├── kpi/
│   ├── ab_tests/
│   ├── mentorship/
│   └── documentation/
├── project_other_project_1234567891/
│   └── ...
└── projects.json  # Метаданные всех проектов
```

### **Глобальные знания:**

```
knowledge/
├── global_knowledge.md  # Знания для всех проектов
└── projects/
    ├── project_atra_trading_1234567890_knowledge.md
    └── project_other_project_1234567891_knowledge.md
```

---

## 🔄 АВТОМАТИЧЕСКИЙ ПРОЦЕСС

### **При работе с проектом:**

1. **Автоматическое переключение контекста**
   - Все системы работают в контексте проекта
   - Данные изолированы между проектами

2. **Обновление знаний:**
   - Глобальные знания обновляются для всех проектов
   - Проект-специфичные знания обновляются отдельно

3. **Обмен знаниями:**
   - Можно делиться знаниями между проектами
   - Общие паттерны применяются ко всем проектам

---

## ✅ ПРЕИМУЩЕСТВА

1. **Изоляция:** Данные проектов не смешиваются
2. **Масштабируемость:** Легко добавлять новые проекты
3. **Гибкость:** Агенты могут работать над несколькими проектами
4. **Знания:** Общие знания применяются ко всем проектам
5. **Специфика:** Каждый проект имеет свои знания

---

## 📈 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### **Сценарий 1: Новый проект**

```bash
# 1. Создать проект
python scripts/manage_projects.py create \
    --name "New Trading Bot" \
    --description "Новый торговый бот" \
    --capabilities ml trading

# 2. Назначить агентов
python scripts/manage_projects.py assign \
    --project-id project_new_trading_bot_1234567890 \
    --agent signal_live \
    --role "Data Analyst" \
    --capabilities ml analysis

# 3. Переключиться на проект
python scripts/manage_projects.py switch \
    --project-id project_new_trading_bot_1234567890
```

### **Сценарий 2: Работа над несколькими проектами**

```python
# Проект 1: ATRA
with project_context("project_atra_trading_1234567890"):
    process_agent_activity("signal_live", "Data Analyst", "signal_generated", True, {...})

# Проект 2: Новый бот
with project_context("project_new_trading_bot_1234567891"):
    process_agent_activity("signal_live", "Data Analyst", "signal_generated", True, {...})
```

---

## ✅ СТАТУС

**Система мультипроектности полностью реализована!** ✅

- ✅ Управление проектами
- ✅ Переключение контекста
- ✅ Изоляция данных
- ✅ Общие и проект-специфичные знания
- ✅ Интеграция во все системы

---

_Документация создана: Виктор (Team Lead)_  
_Дата: 2025-01-XX_
