# 📦 Все модели на Mac Studio M4 Max

**Дата обновления:** 2025-01-21  
**Статус:** ✅ **КОНФИГУРАЦИЯ ОБНОВЛЕНА**

---

## 🎯 ПРИОРИТЕТНЫЕ МОДЕЛИ

Система автоматически выбирает лучшую доступную модель с fallback на менее мощные версии.

### 1. **Reasoning (Сложные задачи, логика)**

**Приоритет:**

1. ✅ `deepseek-r1-distill-llama-70b` (55GB) - **САМЫЙ МОЩНЫЙ** ⭐
2. ⚠️ `llama3.3:70b` (35GB) - альтернатива
3. ✅ `deepseek-r1:7b` (4.7GB) - **УСТАНОВЛЕН** (fallback)

### 2. **Coding (Разработка, код)**

**Приоритет:**

1. ⚠️ `qwen2.5-coder-32b` (35GB) - **САМЫЙ МОЩНЫЙ** ⭐
2. ✅ `qwen2.5-coder:7b` (4.7GB) - **УСТАНОВЛЕН** (fallback)
3. ✅ `qwen2.5-coder:3b` (1.9GB) - **УСТАНОВЛЕН** (быстрый fallback)

### 3. **Fast (Быстрые ответы)**

**Приоритет:**

1. ⚠️ `phi3.5-mini-4k-instruct` (2GB) - **ОПТИМАЛЬНЫЙ** ⭐
2. ⚠️ `phi3-mini-4k-instruct` (2GB) - альтернатива
3. ✅ `phi4:latest` (9.1GB) - **УСТАНОВЛЕН** (но больше)

### 4. **Tiny (Очень быстрые задачи)**

**Приоритет:**

1. ⚠️ `tinyllama:1.1b-chat-v1.0-q4_0` (0.7GB) - **САМЫЙ МАЛЕНЬКИЙ** ⭐
2. ⚠️ `qwen2.5-3b-instruct` (2GB) - альтернатива
3. ✅ `qwen2.5-coder:3b` (1.9GB) - **УСТАНОВЛЕН** (fallback)

### 5. **Vision (Анализ изображений)**

1. ✅ `moondream:latest` (1.7GB) - **УСТАНОВЛЕН**

### 6. **Large (Очень сложные задачи)**

**Приоритет:**

1. ⚠️ `command-r-plus` (65GB) - **ОЧЕНЬ МОЩНАЯ** ⭐⭐
2. ⚠️ `llama3.3:70b` (35GB) - большая модель
3. ⚠️ `qwen2.5-coder-32b` (35GB) - большая модель для кода

---

## 🔧 АВТОМАТИЧЕСКИЙ ВЫБОР

Система автоматически:

1. ✅ Проверяет доступность моделей через Ollama API
2. ✅ Выбирает самую мощную доступную модель
3. ✅ Использует fallback на менее мощные версии
4. ✅ Логирует какой именно выбор был сделан

### Пример работы:

```
🔍 Выбор модели для категории 'reasoning' из 3 вариантов...
   Проверка модели 1/3: deepseek-r1-distill-llama-70b
   ⏭️  Модель deepseek-r1-distill-llama-70b недоступна
   Проверка модели 2/3: llama3.3:70b
   ⏭️  Модель llama3.3:70b недоступна
   Проверка модели 3/3: deepseek-r1:7b
✅ Выбрана модель: deepseek-r1:7b (приоритет 3)
```

---

## 📊 ТЕКУЩИЙ СТАТУС

### ✅ Установлены и работают:

- `deepseek-r1:7b` (4.7GB) - Reasoning fallback
- `qwen2.5-coder:7b` (4.7GB) - Coding fallback
- `qwen2.5-coder:3b` (1.9GB) - Tiny fallback
- `phi4:latest` (9.1GB) - Fast fallback
- `moondream:latest` (1.7GB) - Vision

### ⚠️ Можно установить (приоритетные):

- `deepseek-r1-distill-llama-70b` (55GB) - Reasoning ⭐
- `qwen2.5-coder-32b` (35GB) - Coding ⭐
- `phi3.5-mini-4k-instruct` (2GB) - Fast ⭐
- `tinyllama:1.1b-chat-v1.0-q4_0` (0.7GB) - Tiny ⭐
- `llama3.3:70b` (35GB) - Large ⭐
- `command-r-plus` (65GB) - Very Large ⭐⭐

---

## 🚀 УСТАНОВКА ПРИОРИТЕТНЫХ МОДЕЛЕЙ

```bash
# Reasoning (55GB)
ollama pull deepseek-r1-distill-llama-70b

# Coding (35GB)
ollama pull qwen2.5-coder-32b

# Fast (2GB)
ollama pull phi3.5-mini-4k-instruct

# Tiny (0.7GB)
ollama pull tinyllama:1.1b-chat-v1.0-q4_0

# Large (35GB)
ollama pull llama3.3:70b

# Very Large (65GB)
ollama pull command-r-plus
```

---

## 📋 КОНФИГУРАЦИЯ

### MODEL_PRIORITIES (local_router.py):

```python
MODEL_PRIORITIES = {
    "reasoning": [
        "deepseek-r1-distill-llama-70b",  # 55GB
        "llama3.3:70b",                    # 35GB
        "deepseek-r1:7b",                  # 4.7GB ✅
    ],
    "coding": [
        "qwen2.5-coder-32b",               # 35GB
        "qwen2.5-coder:7b",                # 4.7GB ✅
        "qwen2.5-coder:3b",                # 1.9GB ✅
    ],
    # ...
}
```

---

## ✅ ВСЁ НАСТРОЕНО!

Система автоматически:

- ✅ Выбирает лучшую доступную модель
- ✅ Использует fallback при недоступности
- ✅ Логирует все выборы
- ✅ Работает с текущими моделями
- ✅ Готова использовать более мощные модели после установки

_Конфигурация обновлена командой экспертов ATRA - 2025-01-21_
