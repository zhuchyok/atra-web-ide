# 🔄 СИСТЕМА АВТОМАТИЧЕСКИХ РЕТРОСПЕКТИВ И ОБНОВЛЕНИЯ БАЗЫ ЗНАНИЙ

**Дата создания:** 2025-01-XX  
**Статус:** ✅ **РЕАЛИЗОВАНО**

---

## 🎯 ОПИСАНИЕ

Система автоматически собирает ретроспективы после завершения задач и обновляет базу знаний команды на основе:

- Ретроспектив выполненных задач
- Lessons learned из логов и метрик
- Новых знаний экспертов
- Автоматического анализа сделок

---

## 📁 СТРУКТУРА СИСТЕМЫ

### **Модули:**

1. **`observability/retrospective.py`**
   - Сбор ретроспектив после завершения задач
   - Сохранение в JSON и Markdown форматах
   - Агрегация данных от экспертов

2. **`observability/knowledge_base.py`**
   - Автоматическое обновление `TEAM_SELF_LEARNING_SYSTEM.md`
   - Интеграция новых знаний
   - Группировка по экспертам

3. **`src/monitoring/retrospective_scheduler.py`**
   - Периодический запуск обновления (каждые 24 часа)
   - Автоматический сбор lessons learned

4. **`scripts/auto_retrospective.py`**
   - Скрипт для ручного запуска ретроспектив
   - Интеграция с CI/CD

5. **`scripts/update_knowledge_base.py`**
   - Скрипт для ручного обновления базы знаний

---

## 🚀 ИСПОЛЬЗОВАНИЕ

### **1. Автоматический сбор ретроспективы после задачи:**

```python
from observability.retrospective import collect_retrospective

# После завершения задачи
retrospective = collect_retrospective(
    task_id="task_001",
    task_name="Исправление ML features",
    task_description="Добавление недостающих features в ML модель",
    duration_minutes=45,
    experts_data=[
        {
            "expert": "Дмитрий",
            "role": "ML Engineer",
            "what_worked": [
                "Быстро нашли проблему с feature names",
                "Переобучение модели прошло успешно"
            ],
            "what_to_improve": [
                "Нужно добавить валидацию features перед деплоем"
            ],
            "new_knowledge": [
                "LightGBM требует точного совпадения feature names",
                "ROC AUC 1.0 - отличный результат"
            ],
            "knowledge_updates": [
                "Добавлен чеклист валидации features"
            ]
        }
    ],
    metrics={
        "errors_count": 0,
        "ml_roc_auc": 1.0,
        "features_count": 15
    }
)
```

### **2. Автоматическое обновление базы знаний:**

```python
from observability.knowledge_base import update_knowledge_base

# Обновляет TEAM_SELF_LEARNING_SYSTEM.md
success = update_knowledge_base()
```

### **3. Запуск через скрипт:**

```bash
# Сбор ретроспективы и обновление базы знаний
python scripts/auto_retrospective.py \
    --task-id "task_001" \
    --task-name "Исправление ML features" \
    --task-description "Добавление недостающих features" \
    --duration-minutes 45

# Только обновление базы знаний
python scripts/update_knowledge_base.py
```

### **4. Интеграция в main.py:**

```python
# В main.py добавьте периодическую задачу:
from src.monitoring.retrospective_scheduler import run_retrospective_scheduler_task

# В функции main():
retrospective_task = asyncio.create_task(run_retrospective_scheduler_task())
```

---

## 📊 ФОРМАТ ДАННЫХ

### **Ретроспектива (JSON):**

```json
{
  "task_id": "task_001",
  "task_name": "Исправление ML features",
  "task_description": "Добавление недостающих features",
  "completed_at": "2025-01-XXT12:00:00+00:00",
  "duration_minutes": 45,
  "experts": [
    {
      "expert": "Дмитрий",
      "role": "ML Engineer",
      "what_worked": ["..."],
      "what_to_improve": ["..."],
      "new_knowledge": ["..."],
      "knowledge_updates": ["..."]
    }
  ],
  "overall_what_worked": ["..."],
  "overall_what_to_improve": ["..."],
  "overall_new_knowledge": ["..."],
  "metrics": {...},
  "lessons_learned": ["..."]
}
```

### **Хранение:**

- **JSON ретроспективы:** `retrospectives/{task_id}_{timestamp}.json`
- **Markdown отчеты:** `retrospectives/{task_id}_report.md`
- **База знаний:** `scripts/TEAM_SELF_LEARNING_SYSTEM.md`

---

## 🔄 АВТОМАТИЧЕСКИЙ ПРОЦЕСС

### **Ежедневное обновление (24 часа):**

1. **Сбор lessons learned** из:
   - Trace events (логи агентов)
   - Order audit failures
   - Автоматический анализ сделок
   - Неявный feedback

2. **Обновление базы знаний:**
   - Извлечение новых знаний из ретроспектив
   - Группировка по экспертам
   - Добавление в `TEAM_SELF_LEARNING_SYSTEM.md`

3. **Сохранение:**
   - Резервная копия базы знаний
   - Обновление с меткой времени

---

## 📈 МЕТРИКИ

Система отслеживает:

- Количество ретроспектив
- Новых знаний добавлено
- Улучшений предложено
- Экспертов обновлено

---

## ✅ ПРЕИМУЩЕСТВА

1. **Автоматизация:** Не нужно вручную обновлять базу знаний
2. **Структурированность:** Все знания в одном месте
3. **История:** Сохранение всех ретроспектив
4. **Интеграция:** Автоматический сбор из разных источников
5. **Масштабируемость:** Легко добавить новые источники знаний

---

## 🔧 НАСТРОЙКА

### **Изменение частоты обновления:**

В `src/monitoring/retrospective_scheduler.py`:

```python
# Изменить с 24 часов на 12 часов:
await asyncio.sleep(12 * 60 * 60)  # 12 часов
```

### **Добавление новых источников знаний:**

В `observability/knowledge_base.py`:

```python
def _extract_knowledge_from_custom_source(self):
    # Ваша логика извлечения знаний
    pass
```

---

## 📚 СВЯЗАННЫЕ ДОКУМЕНТЫ

- `scripts/TEAM_SELF_LEARNING_SYSTEM.md` - База знаний команды
- `observability/feedback.py` - Сбор feedback
- `observability/evolution_engine.py` - Эволюция промптов

---

## 🧠 АВТОМАТИЧЕСКОЕ ПРИМЕНЕНИЕ ЗНАНИЙ

### **Система автоматически применяет изученные знания:**

1. **Lessons learned → Guidance**
   - Автоматически обновляет `configs/guidance/<agent>.json`
   - Агенты используют через `get_guidance(agent)`
   - Применяется в реальном времени

2. **Ретроспективы → База знаний**
   - Автоматически обновляет `TEAM_SELF_LEARNING_SYSTEM.md`
   - Группирует знания по экспертам
   - Сохраняет историю

3. **Новые знания → Эволюция промптов**
   - Автоматически эволюционирует промпты агентов
   - Применяет улучшения с приростом >5%
   - Создает резервные копии

### **Автоматический запуск:**

- **Каждые 24 часа:** Планировщик автоматически применяет все знания
- **После задач:** Можно запустить вручную через `scripts/apply_knowledge.py`

### **Ручной запуск:**

```bash
# Применить все изученные знания
python scripts/apply_knowledge.py
```

---

## 🎯 СТАТУС

✅ **Система полностью реализована и готова к использованию!**

- ✅ Модуль ретроспектив
- ✅ Модуль обновления базы знаний
- ✅ Модуль автоматического применения знаний
- ✅ Периодический планировщик (каждые 24 часа)
- ✅ Скрипты для ручного запуска
- ✅ Интеграция в observability
- ✅ Автоматическое применение lessons learned
- ✅ Автоматическая эволюция промптов

---

_Документация создана: Виктор (Team Lead)_  
_Дата: 2025-01-XX_
