# 📖 РУКОВОДСТВО ПО ИСПОЛЬЗОВАНИЮ СИСТЕМ УЛУЧШЕНИЙ АГЕНТОВ

**Дата:** 2025-01-XX  
**Статус:** ✅ **ГОТОВО К ИСПОЛЬЗОВАНИЮ**

---

## 🚀 БЫСТРЫЙ СТАРТ

### **1. Просмотр статуса агентов:**

```bash
python scripts/agent_status.py
```

Показывает:

- Рейтинги и менторство
- KPI и достижения
- Аномалии и предупреждения
- Активные задачи

---

### **2. Применение всех знаний:**

```bash
python scripts/apply_knowledge.py
```

Применяет:

- Lessons learned → Guidance
- Ретроспективы → База знаний
- Новые знания → Эволюция промптов

---

### **3. Сбор ретроспективы:**

```bash
python scripts/auto_retrospective.py \
    --task-id "task_001" \
    --task-name "Оптимизация ML" \
    --task-description "Улучшение модели" \
    --duration-minutes 60
```

---

## 🎯 ИСПОЛЬЗОВАНИЕ В КОДЕ

### **Автоматическое отслеживание активности:**

```python
from observability.agent_tracker import track_agent_activity

@track_agent_activity(
    agent="signal_live",
    role="Data Analyst",
    activity_type="signal_generated",
    extract_metrics=lambda result: {
        "win_rate": result.get("win_rate", 0.0),
        "profit_factor": result.get("profit_factor", 0.0),
    }
)
async def generate_signal(symbol: str):
    # Ваш код генерации сигнала
    return {"win_rate": 0.75, "profit_factor": 2.0}
```

### **Контекстный менеджер для задач:**

```python
from observability.agent_tracker import track_task

with track_task("signal_live", "Data Analyst", "ml_retraining"):
    # Ваш код переобучения ML
    retrain_model()
```

### **Ручная обработка активности:**

```python
from observability.agent_improvements_integration import process_agent_activity

process_agent_activity(
    agent="signal_live",
    role="Data Analyst",
    activity_type="signal_generated",
    success=True,
    metrics={
        "win_rate": 0.75,
        "profit_factor": 2.0,
        "signals_count": 10,
    },
)
```

---

## 📊 РАБОТА С СИСТЕМАМИ

### **Менторство:**

```python
from observability.mentorship import get_mentorship_system

system = get_mentorship_system()
system.update_agent_rating("signal_live", "Data Analyst", success=True, performance=0.9)
mentor = system.assign_mentor("signal_live")
recommendations = system.get_recommendations("signal_live", topic="win_rate")
```

### **A/B тестирование:**

```python
from observability.ab_testing import create_ab_test, get_ab_testing_system

# Создать тест
test = create_ab_test(
    agent="signal_live",
    test_name="new_prompt",
    description="Тест нового промпта",
    variants=[
        {"name": "control", "config": {"prompt": "old"}},
        {"name": "variant_a", "config": {"prompt": "new"}},
    ],
    control_variant="control",
)

# Запустить тест
system = get_ab_testing_system()
system.start_test(test.test_id)

# Записывать результаты
system.record_result(test.test_id, "variant_a", success=True, metrics={"win_rate": 0.80})
system.record_result(test.test_id, "control", success=True, metrics={"win_rate": 0.75})

# Завершить тест
winner = system.complete_test(test.test_id)
```

### **Приоритизация задач:**

```python
from observability.task_prioritizer import get_task_prioritizer, Priority

prioritizer = get_task_prioritizer()
prioritizer.add_task(
    task_id="task_001",
    title="Исправить ML",
    description="...",
    priority=Priority.HIGH,
)

# Автоматическое распределение
prioritizer.auto_assign_tasks({
    "signal_live": ["ml", "analysis"],
    "auto_execution": ["execution", "orders"],
})
```

### **Обнаружение аномалий:**

```python
from observability.anomaly_detector import get_anomaly_detector

detector = get_anomaly_detector()
detector.record_metrics("signal_live", {"win_rate": 0.65, "error_rate": 0.05})
anomalies = detector.detect_anomalies("signal_live")

for anomaly in anomalies:
    print(f"Аномалия: {anomaly.description}")
    print(f"Исправление: {anomaly.suggested_fix}")
```

### **Раннее предупреждение:**

```python
from observability.early_warning import get_early_warning_system

warning_system = get_early_warning_system()
warning_system.record_metrics("signal_live", {"win_rate": 0.70})
warnings = warning_system.analyze_trends("signal_live")

for warning in warnings:
    print(f"Предупреждение: {warning.message}")
    print(f"Предсказанная проблема: {warning.predicted_issue}")
    print(f"Действия: {warning.suggested_actions}")
```

### **KPI:**

```python
from observability.kpi_system import get_kpi_system

kpi_system = get_kpi_system()
kpi_system.update_kpi("signal_live", "Data Analyst", {
    "win_rate": 0.75,
    "profit_factor": 2.1,
})

kpi = kpi_system.get_agent_kpi("signal_live")
print(f"Общий балл: {kpi.overall_score}")
print(f"Достижения: {kpi.achievements}")
```

### **Командная работа:**

```python
from observability.team_work import form_team_for_task, get_team_work_system

# Регистрируем возможности агентов
system = get_team_work_system()
system.register_agent_capabilities("signal_live", ["ml", "analysis", "signals"])
system.register_agent_capabilities("auto_execution", ["execution", "orders"])

# Формируем команду
team = form_team_for_task(
    team_name="ML Optimization",
    objective="Оптимизировать ML модель",
    required_capabilities=["ml", "analysis", "testing"],
)

# Активируем команду
system.activate_team(team.team_id)

# Назначаем задачи
system.assign_task_to_team(team.team_id, "task_001")
```

---

## 🔄 АВТОМАТИЧЕСКИЙ ПРОЦЕСС

Все системы работают автоматически:

- **Каждые 6 часов:** Обновление всех систем
- **При активности агентов:** Автоматическое отслеживание
- **При завершении задач:** Автоматические ретроспективы
- **При обнаружении проблем:** Автоматические алерты

---

## 📈 МОНИТОРИНГ

### **Просмотр статуса:**

```bash
python scripts/agent_status.py
```

### **Применение знаний:**

```bash
python scripts/apply_knowledge.py
```

### **Обновление базы знаний:**

```bash
python scripts/update_knowledge_base.py
```

---

_Документация создана: Виктор (Team Lead)_  
_Дата: 2025-01-XX_
