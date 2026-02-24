# 🎓 Руководство по дообучению локальных моделей

**Дата:** 2026-01-25  
**Статус:** ✅ Реализовано

---

## 🎯 Цели дообучения

1. **Сделать умнее** - улучшить качество ответов на ваших задачах
2. **Сделать шустрее** - оптимизировать скорость работы
3. **Убрать галлюцинации** - снизить количество выдуманных фактов

---

## 📦 Компоненты системы

### 1. Model Fine-Tuner (`knowledge_os/app/model_finetuner.py`)

**Функции:**

- ✅ Сбор данных для обучения из базы знаний
- ✅ Создание датасетов для fine-tuning
- ✅ Дообучение моделей через MLX-LM (LoRA)
- ✅ Оптимизация скорости через квантование

### 2. Anti-Hallucination System (`knowledge_os/app/anti_hallucination.py`)

**Функции:**

- ✅ RAG (Retrieval Augmented Generation) - использование контекста из базы знаний
- ✅ Валидация ответов на галлюцинации
- ✅ Улучшение промптов для снижения выдумок
- ✅ Проверка ответов на основе проверенных фактов

---

## 🚀 Быстрый старт

### Вариант 1: Автоматическое дообучение

```bash
# Дообучить модель qwen2.5-coder:32b
bash scripts/finetune_model.sh qwen2.5-coder:32b

# С параметрами
bash scripts/finetune_model.sh qwen2.5-coder:32b true true
```

### Вариант 2: Через Python

```python
from knowledge_os.app.model_finetuner import ModelFineTuner
import asyncio

async def main():
    tuner = ModelFineTuner()
    results = await tuner.create_finetuning_pipeline(
        model_name="qwen2.5-coder:32b",
        include_anti_hallucination=True,
        include_knowledge_base=True
    )
    print(results)

asyncio.run(main())
```

---

## 📊 Методы улучшения моделей

### 1. Fine-Tuning (Дообучение)

**Что делает:**

- Обучает модель на ваших данных из базы знаний
- Использует LoRA (Low-Rank Adaptation) для эффективности
- Сохраняет базовые знания модели

**Результат:**

- ✅ Лучше понимает ваши задачи
- ✅ Более точные ответы в вашей области
- ✅ Меньше галлюцинаций на знакомых темах

**Время обучения:**

- 7B модель: 10-30 минут (1000 итераций)
- 32B модель: 1-3 часа (1000 итераций)
- 70B модель: 3-6 часов (1000 итераций)

### 2. RAG (Retrieval Augmented Generation)

**Что делает:**

- Ищет релевантный контекст в базе знаний
- Использует проверенные факты для ответов
- Снижает галлюцинации через привязку к источникам

**Результат:**

- ✅ Ответы основаны на проверенных данных
- ✅ Меньше выдумок
- ✅ Можно указать источники

**Использование:**

```python
from knowledge_os.app.anti_hallucination import AntiHallucinationSystem

system = AntiHallucinationSystem()
enhanced = await system.enhance_response_with_rag(
    user_query="Как работает система?",
    model_response="...",
    use_context=True
)
```

### 3. Оптимизация скорости

**Методы:**

- Квантование (Q4_K_M, Q6_K, Q8_0)
- Оптимизация инференса
- Кэширование промптов

**Результат:**

- ✅ Быстрее ответы (2-3x)
- ✅ Меньше использование памяти
- ✅ Больше моделей можно загрузить одновременно

---

## 🎯 Снижение галлюцинаций

### Метод 1: Fine-tuning на проверенных данных

```python
# Собираем только проверенные знания
tuner = ModelFineTuner()
training_data = await tuner.collect_training_data_from_knowledge_base(
    limit=1000  # Только проверенные (confidence >= 0.8)
)

# Дообучаем модель
await tuner.fine_tune_mlx_model(
    base_model="qwen2.5-coder:32b",
    training_data_path="training_data.jsonl",
    output_model_name="qwen2.5-coder:32b-verified"
)
```

### Метод 2: Anti-Hallucination промпты

```python
system = AntiHallucinationSystem()
prompt = system.create_anti_hallucination_prompt(
    user_query="Вопрос",
    context=["Проверенный факт 1", "Проверенный факт 2"]
)
```

### Метод 3: Валидация ответов

```python
is_valid, confidence, issues = await system.validate_response(
    response="Ответ модели",
    context=[{"content": "...", "confidence": 0.9}]
)

if not is_valid:
    # Ответ содержит галлюцинации, нужно улучшить
    print(f"Проблемы: {issues}")
```

---

## 📈 Улучшение скорости

### 1. Использование квантованных моделей

Ваши модели уже квантованы:

- `qwen2.5-coder:32b` - Q8_0 (высокое качество)
- `deepseek-r1-distill-llama:70b` - Q6 (баланс)
- `phi3.5:3.8b` - Q4 (быстро)

### 2. Оптимизация через MLX

MLX автоматически оптимизирует модели для Apple Silicon:

- Использует Neural Engine
- Эффективное использование памяти
- Быстрый инференс

### 3. Кэширование промптов

```python
# Используйте одинаковые промпты для кэширования
# MLX поддерживает prompt caching (до 90% экономии)
```

---

## 🔧 Настройка fine-tuning

### Параметры LoRA

```python
await tuner.fine_tune_mlx_model(
    base_model="qwen2.5-coder:32b",
    training_data_path="data.jsonl",
    output_model_name="custom-model",
    lora_rank=16,        # Ранг адаптера (больше = лучше, но медленнее)
    lora_alpha=32,       # Альфа параметр
    batch_size=4,        # Размер батча
    learning_rate=1e-4,  # Скорость обучения
    num_epochs=3         # Количество эпох
)
```

### Рекомендации

| Параметр        | Малые модели (3-7B) | Средние (13-32B) | Большие (70B+) |
| --------------- | ------------------- | ---------------- | -------------- |
| `lora_rank`     | 8-16                | 16-32            | 32-64          |
| `batch_size`    | 4-8                 | 2-4              | 1-2            |
| `learning_rate` | 1e-4                | 5e-5             | 1e-5           |
| `num_epochs`    | 3-5                 | 2-3              | 1-2            |

---

## 📊 Сбор данных для обучения

### Из базы знаний

```python
# Проверенные знания (confidence >= 0.8)
data = await tuner.collect_training_data_from_knowledge_base(limit=1000)

# Против галлюцинаций (только факты)
ah_data = await tuner.collect_anti_hallucination_data()
```

### Формат данных

```json
{
  "instruction": "Напиши код для задачи",
  "input": "",
  "output": "def solution(): ...",
  "domain": "Coding",
  "confidence": 0.95,
  "metadata": { "type": "code_example", "verified": true }
}
```

---

## ✅ Чек-лист дообучения

- [ ] Установлен MLX-LM: `pip install mlx-lm`
- [ ] Собраны данные для обучения (минимум 100 примеров)
- [ ] Выбрана базовая модель
- [ ] Настроены параметры LoRA
- [ ] Запущено дообучение
- [ ] Проверено качество новой модели
- [ ] Интегрирована в систему

---

## 🐛 Устранение неполадок

### Ошибка: "MLX-LM не установлен"

```bash
pip3 install mlx-lm
```

### Ошибка: "Недостаточно памяти"

- Уменьшите `batch_size`
- Используйте более агрессивное квантование
- Обучайте на меньшей модели сначала

### Ошибка: "Недостаточно данных"

- Соберите больше данных из базы знаний
- Используйте `include_knowledge_base=True`
- Минимум 100 примеров для начала

---

## 📝 Примеры использования

### Пример 1: Дообучение для кодирования

```python
tuner = ModelFineTuner()
results = await tuner.create_finetuning_pipeline(
    model_name="qwen2.5-coder:32b",
    include_anti_hallucination=True,
    include_knowledge_base=True
)
```

### Пример 2: Снижение галлюцинаций через RAG

```python
system = AntiHallucinationSystem()
enhanced = await system.enhance_response_with_rag(
    user_query="Как работает система?",
    model_response="Система работает так...",
    use_context=True
)
```

### Пример 3: Валидация ответа

```python
is_valid, confidence, issues = await system.validate_response(
    response="Ответ модели",
    context=[{"content": "Проверенный факт", "confidence": 0.95}]
)

if not is_valid:
    print(f"⚠️ Обнаружены проблемы: {issues}")
```

---

## 🎯 Рекомендации

1. **Начните с малых моделей** (3-7B) для тестирования
2. **Используйте проверенные данные** (confidence >= 0.8)
3. **Комбинируйте методы**: Fine-tuning + RAG + валидация
4. **Тестируйте на реальных задачах** перед деплоем
5. **Мониторьте качество** после дообучения

---

**Версия:** 1.0  
**Обновлено:** 2026-01-25
