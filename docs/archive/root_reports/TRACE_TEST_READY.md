# ✅ Детальное тестирование готово

**Дата:** 2026-01-26  
**Статус:** ✅ **ГОТОВО К ЗАПУСКУ**

---

## 🚀 ЗАПУСК

```bash
cd /Users/bikos/Documents/atra-web-ide
python3 scripts/test_task_distribution_trace.py
```

---

## 📊 ЧТО ОТСЛЕЖИВАЕТСЯ

### 1. 🤖 Выбор моделей:

- **Victoria** → модель для анализа задачи (ExtendedThinkingEngine или run_smart_agent_async)
- **Сотрудники** → каждый выбирает модель для своей задачи
  - По рекомендациям Victoria
  - Автоматически на основе типа задачи
  - По умолчанию

### 2. 💬 Промпты:

- Промпт Victoria для анализа задачи
- Промпт Victoria для Veronica (с распределением)
- Промпт для каждого сотрудника
- Промпт для валидации
- Промпт для синтеза

### 3. 🎯 Решения:

- Выбор отдела
- Выбор сотрудника
- Выбор модели
- Решение о валидации
- Решение об эскалации

### 4. 📋 Этапы:

- INIT → VICTORIA_INIT → TASK_START → ... → TASK_COMPLETE

---

## 📄 РЕЗУЛЬТАТЫ

### Файлы:

1. `logs/task_trace_YYYYMMDD_HHMMSS.log` - детальный лог
2. `logs/task_trace_result_YYYYMMDD_HHMMSS.json` - JSON трейс

### В JSON будет:

```json
{
  "start_time": "...",
  "end_time": "...",
  "duration_seconds": 45.2,
  "stages": [...],
  "model_selections": [
    {
      "who": "Victoria",
      "task": "...",
      "selected_model": "ExtendedThinkingEngine",
      "reason": "...",
      "available_models": [...]
    }
  ],
  "prompts": [...],
  "decisions": [...]
}
```

---

## 🔍 ЧТО ИСКАТЬ В ЛОГАХ

1. **🤖 [MODEL]** - выбор модели
2. **💬 [PROMPT]** - промпт
3. **🎯 [DECISION]** - решение
4. **📋 [STAGE]** - этап

---

**Готово! Запускай тест!**
