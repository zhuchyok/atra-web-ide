# ✅ Конфигурация: Использование локальных моделей Mac Studio

**Дата:** 2025-01-21  
**Статус:** ✅ **ДА, МЫ ИСПОЛЬЗУЕМ ЛОКАЛЬНЫЕ МОДЕЛИ НА MAC STUDIO**

---

## 🎯 ОТВЕТ: ДА, МЫ ИСПОЛЬЗУЕМ ЛОКАЛЬНЫЕ МОДЕЛИ

### ✅ Настроено для использования Mac Studio:

1. **Основной узел:** Mac Studio M4 Max (приоритет 1)
   - URL: `http://localhost:11434` (MLX API Server)
   - Production модели установлены и доступны

2. **USE_LOCAL_LLM:** `true` (по умолчанию)
   - Система использует локальные модели как приоритет

3. **MODEL_MAP:** Все настроено на production модели Mac Studio:
   - `complex/enterprise`: `command-r-plus:104b` (~65GB)
   - `reasoning`: `deepseek-r1-distill-llama:70b` (~40GB)
   - `complex`: `llama3.3:70b` (~40GB)
   - `coding (high quality)`: `qwen2.5-coder:32b` (~20GB)
   - `fast/general`: `phi3.5:3.8b` (~2.5GB)
   - `fast (lightweight)`: `phi3:mini-4k` (~2GB)
   - `fast/default`: `qwen2.5:3b` (~2GB)
   - `fast (ultra-lightweight)`: `tinyllama:1.1b-chat` (~700MB)

---

## 🔧 КОНФИГУРАЦИЯ

### LocalAIRouter:

```python
# Основной узел (приоритет 1)
self.nodes = [
    {
        "name": "Mac Studio M4 Max",
        "url": "http://localhost:11434",  # MLX API Server
        "priority": 1,
        "routing_key": "mac_studio",
        "type": "primary"
    },
    # Fallback узлы (только если Mac Studio недоступен)
    ...
]
```

### Использование:

- ✅ **USE_LOCAL_LLM = true** - локальные модели включены
- ✅ **Mac Studio = приоритет 1** - используется в первую очередь
- ✅ **Fallback узлы** - только если Mac Studio недоступен

---

## 📊 ПРИОРИТЕТЫ

1. **Приоритет 1:** Mac Studio M4 Max (`localhost:11434`)
   - Production модели (131GB, 61GB, и т.д.)
   - Самый мощный

2. **Приоритет 2:** Mac Studio (fallback)
   - Используется только если Mac Studio недоступен

3. **Приоритет 3:** Server (legacy fallback)
   - Используется только если Mac Studio и Mac Studio недоступны

---

## ✅ КОМПОНЕНТЫ, ИСПОЛЬЗУЮЩИЕ MAC STUDIO:

1. ✅ **LocalAIRouter** - основной роутер
2. ✅ **VeronicaWebResearcher** - веб-исследователь
3. ✅ **NightlyLearner** - обучение экспертов
4. ✅ **AI Core** - обработка запросов агентов
5. ✅ Все агенты (Victoria, Veronica) - через LocalAIRouter

---

## 🎯 ИТОГ:

**ДА, мы используем локальные модели на Mac Studio!**

- ✅ Все production модели доступны
- ✅ Mac Studio - приоритет 1 (основной)
- ✅ Система настроена автоматически использовать их
- ✅ Fallback на другие узлы только при недоступности

---

_Конфигурация проверена командой экспертов ATRA - 2025-01-21_
