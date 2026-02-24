# ✅ Ollama модели на Mac Studio M4 Max

**Дата проверки:** 2025-01-21  
**Статус:** ✅ **УСТАНОВЛЕНЫ И РАБОТАЮТ**

---

## 📦 УСТАНОВЛЕННЫЕ МОДЕЛИ

### 1. **deepseek-r1:7b** (4.7 GB) - Reasoning

- **Размер:** 7.6B параметров
- **Назначение:** Reasoning, сложные задачи
- **Статус:** ✅ Работает

### 2. **qwen2.5-coder:7b** (4.7 GB) - Coding

- **Размер:** 7.6B параметров
- **Назначение:** Кодирование, разработка
- **Статус:** ✅ Работает

### 3. **phi4:latest** (9.1 GB) - Fast/Balanced

- **Размер:** 14.7B параметров
- **Назначение:** Универсальные задачи, быстрые ответы
- **Статус:** ✅ Работает

### 4. **qwen2.5-coder:3b** (1.9 GB) - Tiny/Fast

- **Размер:** 3.1B параметров
- **Назначение:** Быстрые задачи, легкие модели
- **Статус:** ✅ Работает

### 5. **moondream:latest** (1.7 GB) - Vision

- **Размер:** 1B параметров
- **Назначение:** Vision tasks, анализ изображений
- **Статус:** ✅ Работает

### 6. **nomic-embed-text:latest** (274 MB) - Embeddings

- **Размер:** 137M параметров
- **Назначение:** Text embeddings, векторный поиск
- **Статус:** ✅ Работает

---

## 🔧 КОНФИГУРАЦИЯ

### MODEL_MAP (local_router.py):

```python
MODEL_MAP = {
    "coding": "qwen2.5-coder:7b",      # 7.6B параметров
    "reasoning": "deepseek-r1:7b",      # 7.6B параметров
    "fast": "phi4:latest",              # 14.7B параметров (самая большая!)
    "tiny": "qwen2.5-coder:3b",         # 3.1B параметров
    "vision": "moondream:latest",       # 1B параметров
    "default": "qwen2.5-coder:7b"       # 7.6B параметров
}
```

### URL конфигурация:

```python
MAC_STUDIO_LLM_URL = "http://localhost:11434"  # Ollama на Mac Studio
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Проверка Ollama API:

```bash
curl http://localhost:11434/api/tags
```

### Тест генерации:

```bash
curl -s http://localhost:11434/api/generate \
  -d '{"model": "deepseek-r1:7b", "prompt": "test", "stream": false}'
```

### Проверка запущенных процессов:

```bash
ps aux | grep ollama
```

---

## 📊 СТАТИСТИКА

- **Всего моделей:** 6
- **Общий размер:** ~22.6 GB
- **Ollama статус:** ✅ Работает на localhost:11434
- **Процессы:** 4 активных процесса Ollama

---

## 🎯 ИСПОЛЬЗОВАНИЕ

### Через Knowledge OS:

- Все агенты (Victoria, Veronica) автоматически используют Ollama модели
- Автоматический выбор модели по категории задачи
- Fallback на другие узлы при недоступности

### Напрямую через API:

```python
import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5-coder:7b",
        "prompt": "Напиши функцию на Python",
        "stream": False
    }
)
print(response.json()["response"])
```

---

## ✅ ВСЁ РАБОТАЕТ!

Все модели установлены, протестированы и готовы к использованию.

_Проверено командой экспертов ATRA - 2025-01-21_
