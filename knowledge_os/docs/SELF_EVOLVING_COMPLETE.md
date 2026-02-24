# ✅ Self-Evolving System (L4) - завершено

**Дата:** 2025-11-13  
**Статус:** ✅ **ГОТОВО**

---

## 🎯 Что реализовано

### 1. EvolutionEngine - движок эволюции промптов

**Файл:** `observability/evolution_engine.py`

**Компоненты:**

- ✅ `analyze_agent_performance()` - анализ производительности агента
- ✅ `generate_prompt_improvements()` - генерация улучшений
- ✅ `create_prompt_variant()` - создание вариантов промптов
- ✅ `evaluate_variant()` - оценка вариантов
- ✅ `apply_evolution()` - применение эволюции

**Функциональность:**

- Анализ производительности на основе lessons learned
- Генерация улучшений промптов
- Создание вариантов с улучшениями
- Оценка и сравнение вариантов
- Автоматическое применение лучших вариантов

### 2. Скрипт эволюции

**Файл:** `scripts/evolve_prompts.py`

**Использование:**

```bash
# Эволюция всех агентов
python3 scripts/evolve_prompts.py

# Эволюция конкретного агента
python3 scripts/evolve_prompts.py --agent signal_live

# Применить эволюцию автоматически
python3 scripts/evolve_prompts.py --apply

# Настроить минимальный прирост
python3 scripts/evolve_prompts.py --min-gain 0.10
```

---

## 📊 Как это работает

### Процесс эволюции:

1. **Анализ производительности:**

   ```python
   performance = engine.analyze_agent_performance("signal_live")
   # Результат: {
   #   "has_lessons": True,
   #   "total_issues": 15,
   #   "critical_issues": 3,
   #   "performance_score": 0.85,
   #   "lessons": [...]
   # }
   ```

2. **Генерация улучшений:**

   ```python
   improvements = engine.generate_prompt_improvements(
       agent="signal_live",
       current_prompt=current_prompt,
       lessons=lessons,
   )
   # Результат: [
   #   "Добавить проверку для предотвращения: rsi_overbought_long",
   #   "Усилить фильтры для: low_volume",
   #   ...
   # ]
   ```

3. **Создание варианта:**

   ```python
   variant = engine.create_prompt_variant(
       agent="signal_live",
       improvements=improvements,
       lessons=lessons,
   )
   # Результат: PromptVariant с новой версией промпта
   ```

4. **Оценка варианта:**

   ```python
   variant_performance = engine.evaluate_variant(variant, performance)
   # Результат: 0.92 (улучшение на 7%)
   ```

5. **Применение эволюции:**
   ```python
   if engine.should_apply_variant(current_performance, variant_performance):
       engine.apply_evolution(result)
   ```

---

## 🔄 Интеграция с Guidance System

EvolutionEngine интегрирован с Guidance System:

- Использует `get_guidance()` для получения lessons learned
- Анализирует проблемы и рекомендации
- Генерирует улучшения на основе рекомендаций
- Применяет улучшения в промптах

---

## 📈 Метрики

- **Минимум уроков для эволюции:** 3
- **Минимальный прирост производительности:** 5% (по умолчанию)
- **Оценка производительности:** 0.0 - 1.0
  - Базовый score из метрик
  - Бонус за количество улучшений
  - Учет success rate из тестов

---

## 🚀 Преимущества

1. **Автоматизация:** Эволюция происходит автоматически
2. **Обучение:** Система учится на основе lessons learned
3. **Безопасность:** Резервные копии перед применением
4. **Гибкость:** Настраиваемые пороги и параметры

---

## 🔄 Следующие шаги

1. **A/B тестирование:** Реализация полноценного A/B тестирования
2. **LLM интеграция:** Использование LLM для генерации улучшений
3. **Метрики производительности:** Расширенный сбор метрик
4. **Автоматический запуск:** Интеграция в cron/scheduler

---

**См. также:**

- [AGENT_DEVELOPMENT_ROADMAP.md](./AGENT_DEVELOPMENT_ROADMAP.md) - полный план развития
- [AGENT_OPS_COMPLETE.md](./AGENT_OPS_COMPLETE.md) - Agent Ops
