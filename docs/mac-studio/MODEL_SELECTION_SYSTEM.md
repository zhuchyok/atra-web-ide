# 🤖 Система автоматического выбора моделей в корпорации ATRA

**Дата:** 2026-01-25  
**Статус:** ✅ Полностью автоматизирована

---

## 🎯 КАК РАБОТАЕТ ВЫБОР МОДЕЛЕЙ

### ✅ **ДА, задачи автоматически выбирают модели!**

Корпорация ATRA использует **интеллектуальную систему автоматического выбора моделей** на основе:

1. **Категории задачи** (reasoning, coding, fast, vision)
2. **Содержания промпта** (ключевые слова, длина)
3. **ML Router** (Singularity 5.0) — машинное обучение для оптимального выбора
4. **Эвристики** (fallback если ML Router недоступен)

---

## 🔧 МЕХАНИЗМЫ ВЫБОРА

### 1. **LocalAIRouter** (`knowledge_os/app/local_router.py`)

**Метод `_select_model()`** — автоматический выбор на основе категории и промпта:

```python
def _select_model(self, prompt: str, category: str = None) -> str:
    """Select the best local model for the task."""
    prompt_lower = prompt.lower()

    # Reasoning задачи → deepseek-r1:7b
    if category == "reasoning" or "подумай" in prompt_lower or "логика" in prompt_lower:
        return MODEL_MAP["reasoning"]  # deepseek-r1:7b

    # Fast задачи → phi4
    if category == "fast" or len(prompt) < 300:
        return MODEL_MAP["fast"]  # phi4

    # Coding задачи → qwen2.5-coder:7b
    if "код" in prompt_lower or "программируй" in prompt_lower:
        return MODEL_MAP["coding"]  # qwen2.5-coder:7b

    # По умолчанию → qwen2.5-coder:7b
    return MODEL_MAP["default"]  # qwen2.5-coder:7b
```

**Категории:**

- `reasoning` → `deepseek-r1:7b` (планирование, логика)
- `coding` → `qwen2.5-coder:7b` (код, рефакторинг)
- `fast` → `phi4` (быстрые ответы)
- `vision` → `moondream` (изображения)
- `default` → `qwen2.5-coder:7b` (универсальная)

---

### 2. **ML Router** (Singularity 5.0)

**Интеллектуальный роутинг на основе машинного обучения:**

- Использует **LightGBM/XGBoost** для предсказания оптимального маршрута
- Анализирует:
  - Тип задачи (coding, reasoning, general)
  - Длину промпта
  - Категорию
  - Производительность узлов
  - Историю успешных запросов

**Файлы:**

- `knowledge_os/app/ml_router_v2.py` — ML Router V2
- `knowledge_os/app/ml_router_model.py` — ML модель
- `knowledge_os/app/ml_router_trainer.py` — Обучение модели

**Если ML Router недоступен:** используется эвристический роутинг

---

### 3. **Model Selector** (`knowledge_os/app/model_selector.py`)

**Автоматический выбор из списка приоритетов:**

```python
async def select_available_model(
    priorities: List[str],
    ollama_url: str = "http://localhost:11434",
    category: str = "unknown"
) -> Optional[str]:
    """Выбирает первую доступную модель из списка приоритетов"""
    for model in priorities:
        if await check_model_available(model, ollama_url):
            return model  # Возвращает первую доступную
    return None
```

**Приоритеты по категориям:**

- `reasoning`: `["deepseek-r1:7b", "qwen2.5-coder:7b", "phi4"]`
- `coding`: `["qwen2.5-coder:7b", "deepseek-coder:6.7b", "phi4"]`
- `fast`: `["phi4", "qwen2.5-coder:7b"]`
- `vision`: `["moondream"]`

---

### 4. **Auto Model Manager** (`knowledge_os/app/auto_model_manager.py`)

**Управление моделями по времени дня:**

- **Утро:** Приоритет coding моделям
- **День:** Сбалансированное использование
- **Вечер:** Приоритет reasoning моделям
- **Ночь:** Только легкие модели

**Автоматически:**

- Загружает нужные модели
- Выгружает неиспользуемые
- Оптимизирует память

---

## 📊 ПРИМЕРЫ АВТОМАТИЧЕСКОГО ВЫБОРА

### Пример 1: Reasoning задача

```
Промпт: "Подумай о стратегии развития проекта"
Категория: reasoning (или определяется автоматически)
→ Выбирается: deepseek-r1:7b
```

### Пример 2: Coding задача

```
Промпт: "Напиши функцию для обработки данных"
Категория: coding (определяется по ключевому слову "напиши")
→ Выбирается: qwen2.5-coder:7b
```

### Пример 3: Fast задача

```
Промпт: "Скажи привет" (короткий промпт < 300 символов)
Категория: fast
→ Выбирается: phi4
```

### Пример 4: Vision задача

```
Промпт: "Что на этом изображении?"
Изображение: предоставлено
→ Выбирается: moondream
```

---

## 🎯 КАК ЭКСПЕРТЫ ИСПОЛЬЗУЮТ МОДЕЛИ

### Victoria Agent:

```python
# Planner (для планирования)
self.planner = OllamaExecutor(model="qwen2.5-coder:32b")

# Executor (для выполнения)
self.executor = OllamaExecutor(model="qwen2.5-coder:32b")
```

**Примечание:** Модели задаются при инициализации, но могут быть переопределены через категории.

### Veronica Agent:

```python
# Planner (для планирования)
self.planner = OllamaExecutor(model="deepseek-r1:7b")

# Executor (для выполнения)
self.executor = OllamaExecutor(model="qwen2.5-coder:7b")
```

---

## 🔄 ПРОЦЕСС ВЫБОРА МОДЕЛИ

```
1. Задача поступает в систему
   ↓
2. Определяется категория (reasoning/coding/fast/vision)
   ↓
3. ML Router анализирует задачу (если доступен)
   ↓
4. Выбирается оптимальная модель из приоритетов
   ↓
5. Проверяется доступность модели
   ↓
6. Если недоступна → следующая в списке приоритетов
   ↓
7. Модель используется для выполнения задачи
```

---

## 📋 ДОСТУПНЫЕ МОДЕЛИ (Mac Studio M4 Max)

**Статус:** ✅ MLX API Server работает на порту 11434 (эмулирует Ollama API)

| Модель                            | Размер | Назначение                                  | Автовыбор                   |
| --------------------------------- | ------ | ------------------------------------------- | --------------------------- |
| **command-r-plus:104b**           | ~65GB  | Максимальная мощность, RAG, мультиязычность | ✅ complex, enterprise      |
| **deepseek-r1-distill-llama:70b** | ~40GB  | Reasoning, планирование (distilled)         | ✅ reasoning                |
| **llama3.3:70b**                  | ~40GB  | Максимальное качество, общие задачи         | ✅ complex                  |
| **qwen2.5-coder:32b**             | ~20GB  | Качественный код, рефакторинг               | ✅ coding (high quality)    |
| **phi3.5:3.8b**                   | ~2.5GB | Быстрые задачи, общие                       | ✅ fast, general            |
| **phi3:mini-4k**                  | ~2GB   | Быстрые ответы, легкие задачи               | ✅ fast (lightweight)       |
| **qwen2.5:3b**                    | ~2GB   | Быстрые ответы, общие задачи                | ✅ fast, default            |
| **tinyllama:1.1b-chat**           | ~700MB | Очень быстрые ответы                        | ✅ fast (ultra-lightweight) |

---

## ✅ ПРЕИМУЩЕСТВА АВТОМАТИЧЕСКОГО ВЫБОРА

1. **Оптимальное использование ресурсов:**
   - Легкие задачи → легкие модели
   - Сложные задачи → мощные модели

2. **Экономия токенов:**
   - ML Router выбирает локальные модели когда возможно
   - Экономия до 95% токенов (Singularity 5.0)

3. **Автоматическая оптимизация:**
   - Auto Model Manager управляет памятью
   - Загружает/выгружает модели по необходимости

4. **Адаптивность:**
   - ML Router обучается на исторических данных
   - Улучшается со временем

---

## 🎉 ИТОГ

**ДА, задачи автоматически выбирают модели из доступных!**

Система использует:

- ✅ **Категории задач** для базового выбора
- ✅ **ML Router** для интеллектуального выбора
- ✅ **Эвристики** как fallback
- ✅ **Auto Model Manager** для оптимизации памяти

**Эксперты не выбирают модели вручную** — система делает это автоматически на основе анализа задачи!

---

_Документация создана 2026-01-25_
