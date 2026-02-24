# Статус Ollama моделей

**Дата проверки:** 2026-01-27

## ✅ Установленные модели

### Проверено и работает:

- ✅ **moondream:latest** (1.7 GB) - Vision модель для скриншотов
- ✅ **tinyllama:1.1b-chat** (637 MB) - Очень быстрая текстовая модель

### Требует проверки:

- ⚠️ **llava:7b** (4.7 GB) - Vision модель для PDF
  - API показывает что установлена, но не видна в `ollama list`
  - Проверка: `ollama show llava:7b`
- ⚠️ **phi3.5:3.8b** (2.5 GB) - Быстрая текстовая модель
  - API показывает что установлена, но не видна в `ollama list`
  - Проверка: `ollama show phi3.5:3.8b`

## 📋 Команды для проверки

```bash
# Список всех установленных моделей
ollama list

# Проверка конкретной модели
ollama show moondream
ollama show llava:7b
ollama show phi3.5:3.8b
ollama show tinyllama:1.1b-chat

# Установка недостающих моделей
ollama pull llava:7b
ollama pull phi3.5:3.8b
```

## 🔧 Конфигурация в коде

Модели настроены в `knowledge_os/app/local_router.py`:

```python
OLLAMA_MODELS = {
    "fast": "phi3.5:3.8b",      # Быстрая модель (2.5 GB)
    "vision": "moondream",      # Vision модель (1.6 GB)
    "vision_pdf": "llava:7b",    # Vision для PDF (4.7 GB)
    "coding": "phi3.5:3.8b",    # Для простого кода
    "reasoning": "phi3.5:3.8b", # Для простого reasoning
    "default": "phi3.5:3.8b"    # По умолчанию
}
```

## 🎯 Использование

### Автоматическое перераспределение:

- При перегрузке MLX простые задачи автоматически переключаются на Ollama
- Vision задачи используют `moondream` (скриншоты) или `llava:7b` (PDF)
- Простые текстовые задачи используют `phi3.5:3.8b`

### Fallback логика:

1. MLX API Server (приоритет)
2. Ollama (при перегрузке MLX или недоступности)
3. Облако (последний fallback)

## ⚠️ Замечания

- MLX API Server показывает rate limit - это нормально при активном использовании
- Moondream Station не запущен (порт 2020) - можно запустить при необходимости
- Все модели доступны через API, даже если не видны в `ollama list`
