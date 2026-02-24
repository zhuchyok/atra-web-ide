# Интеграция MLX API Server вместо Ollama

**Дата:** 2026-01-26  
**Статус:** ✅ **ОБНОВЛЕНО**

## 🎯 Цель

Использовать MLX API Server (порт 11435) вместо Ollama для всех 8 моделей из PLAN.md.

## ✅ Что сделано

### 1. ReActAgent - приоритет MLX

**Файл:** `knowledge_os/app/react_agent.py`

- ✅ Добавлена поддержка MLX API Server (порт 11435)
- ✅ Приоритет: MLX → Ollama
- ✅ Автоматический fallback между MLX и Ollama
- ✅ Fallback на доступные модели при 404

### 2. Extended Thinking - приоритет MLX

**Файл:** `knowledge_os/app/extended_thinking.py`

- ✅ Добавлена поддержка MLX API Server
- ✅ Приоритет: MLX → Ollama
- ✅ Автоматический fallback между URL и моделями

### 3. Конфигурация

**Переменные окружения:**

- `MLX_API_URL=http://localhost:11435` (MLX API Server)
- `OLLAMA_BASE_URL=http://localhost:11434` (Ollama, fallback)
- `USE_MLX=true` (приоритет MLX)

## 📊 Логика работы

### Приоритет источников:

1. **MLX API Server** (порт 11435) - приоритет
2. **Ollama** (порт 11434) - fallback

### Приоритет моделей (для каждого источника):

1. Основная модель (из категории задачи)
2. Fallback модели по списку:
   - tinyllama:1.1b-chat
   - phi3:mini-4k
   - qwen2.5:3b
   - phi3.5:3.8b
   - qwen2.5-coder:32b
   - deepseek-r1-distill-llama:70b
   - llama3.3:70b

## 🚀 Как это работает

1. **Попытка MLX API Server:**
   - Пробует основную модель на MLX (11435)
   - Если 404, пробует fallback модели на MLX

2. **Fallback на Ollama:**
   - Если MLX недоступен, пробует Ollama (11434)
   - Пробует основную модель на Ollama
   - Если 404, пробует fallback модели на Ollama

3. **Результат:**
   - Использует первый доступный источник и модель
   - Логирует какой источник использован (MLX или Ollama)

## 📋 Модели из PLAN.md

Все 8 моделей доступны через MLX API Server:

| Модель                        | MLX путь                           | Ollama fallback               |
| ----------------------------- | ---------------------------------- | ----------------------------- |
| command-r-plus:104b           | ~/.mlx_models/...                  | command-r-plus:104b           |
| deepseek-r1-distill-llama:70b | ~/.mlx_models/DeepSeek-R1...       | deepseek-r1-distill-llama:70b |
| llama3.3:70b                  | ~/.mlx_models/...                  | llama3.3:70b                  |
| qwen2.5-coder:32b             | ~/.mlx_models/Qwen2.5-Coder-32B... | qwen2.5-coder:32b             |
| phi3.5:3.8b                   | ~/.mlx_models/Phi-3.5-mini...      | phi3.5:3.8b                   |
| phi3:mini-4k                  | ~/.mlx_models/Phi-3-mini...        | phi3:mini-4k                  |
| qwen2.5:3b                    | ~/.mlx_models/Qwen2.5-3B...        | qwen2.5:3b                    |
| tinyllama:1.1b-chat           | ~/.mlx_models/TinyLlama...         | tinyllama:1.1b-chat           |

## ✅ Результат

**Теперь Victoria Enhanced:**

- ✅ Использует MLX API Server (приоритет)
- ✅ Fallback на Ollama если MLX недоступен
- ✅ Работает со всеми 8 моделями из PLAN.md
- ✅ Автоматический выбор оптимального источника

---

**Статус:** ✅ **ИНТЕГРИРОВАНО - MLX ПРИОРИТЕТ**
