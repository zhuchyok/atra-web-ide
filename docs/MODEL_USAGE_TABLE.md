# 📊 ИТОГОВАЯ ТАБЛИЦА ИСПОЛЬЗОВАНИЯ МОДЕЛЕЙ

**Дата обновления:** 2026-01-28  
**Автоматическое сканирование:** `scripts/scan_available_models.py` + `scripts/model_usage_report.py`

---

## ✅ ДОСТУПНЫЕ МОДЕЛИ (Mac Studio)

### MLX API Server (порт 11435):
- `qwen2.5-coder:32b` - coding (high quality)
- `deepseek-r1-distill-llama:70b` - reasoning
- `llama3.3:70b` - complex
- `command-r-plus:104b` - enterprise
- `phi3.5:3.8b` - fast
- `phi3:mini-4k` - fast lightweight
- `qwen2.5:3b` - fast default
- `tinyllama:1.1b-chat` - tiny

### Ollama (порт 11434):
- `glm-4.7-flash:latest` - coding/reasoning (SWE-bench: 59.2%)
- `phi3.5:3.8b` - fast/planner
- `llava:7b` - vision
- `moondream:latest` - vision
- `tinyllama:1.1b-chat` - tiny

---

## 📋 ИТОГОВАЯ ТАБЛИЦА ИСПОЛЬЗОВАНИЯ МОДЕЛЕЙ

| Компонент | Executor Модель | Planner Модель | Роутер |
|-----------|----------------|----------------|--------|
| **Оркестратор** | `deepseek-r1-distill-llama:70b` (reasoning) или `glm-4.7-flash:latest` (через LocalAIRouter) | - | ✅ LocalAIRouter |
| **Victoria** | `qwen2.5-coder:32b` (MLX) | `phi3.5:3.8b` (Ollama) | ✅ LocalAIRouter |
| **Veronica** | `qwen2.5-coder:32b` (MLX) | `phi3.5:3.8b` (Ollama) | ✅ LocalAIRouter |
| **AI Core** | Автовыбор по category (`qwen2.5-coder:32b` / `glm-4.7-flash:latest`) | - | ✅ LocalAIRouter |
| **Local Router** | Автовыбор по category (MLX приоритет → Ollama fallback) | - | ✅ (сам роутер) |
| **Smart Worker** | Автовыбор по category (через LocalAIRouter) | - | ✅ LocalAIRouter |

---

## 🔧 КОНФИГУРАЦИЯ МОДЕЛЕЙ

### Victoria Agent (`src/agents/bridge/victoria_server.py`):
```python
VICTORIA_MODEL=qwen2.5-coder:32b  # MLX модель (Mac Studio)
VICTORIA_PLANNER_MODEL=phi3.5:3.8b  # Ollama модель (Mac Studio)
VICTORIA_USE_LOCAL_ROUTER=true  # Использует LocalAIRouter
```

### Veronica Agent (`src/agents/bridge/server.py`):
```python
VERONICA_USE_LOCAL_ROUTER=true  # Использует LocalAIRouter (как Victoria)
Executor: qwen2.5-coder:32b  # MLX модель (Mac Studio) через LocalAIRouter
Planner: phi3.5:3.8b  # Ollama модель (Mac Studio)
```

### Orchestrator (`knowledge_os/app/orchestrator.py`):
```python
category="reasoning" → deepseek-r1-distill-llama:70b (MLX) или glm-4.7-flash (Ollama)
category="coding" → qwen2.5-coder:32b (MLX) или glm-4.7-flash (Ollama)
```

### Local Router (`knowledge_os/app/local_router.py`):
```python
MODEL_MAP = {
    "coding": "qwen2.5-coder:32b",  # MLX (Mac Studio)
    "reasoning": "deepseek-r1-distill-llama:70b",  # MLX (Mac Studio)
    "fast": "phi3.5:3.8b",  # Ollama
    "default": "phi3.5:3.8b"  # Ollama
}

OLLAMA_MODELS = {
    "coding": "glm-4.7-flash",  # Fallback если MLX недоступен
    "reasoning": "glm-4.7-flash",  # Fallback если MLX недоступен
    "fast": "phi3.5:3.8b",
    "default": "phi3.5:3.8b"
}
```

---

## 🔄 АВТОМАТИЧЕСКОЕ ОТСЛЕЖИВАНИЕ

### Скрипты мониторинга:
1. **`scripts/scan_available_models.py`** - сканирует MLX и Ollama
2. **`scripts/model_usage_report.py`** - генерирует отчет об использовании
3. **`scripts/monitor_models.sh`** - периодический мониторинг (каждый час)

### Запуск:
```bash
# Разовое сканирование
python3 scripts/scan_available_models.py
python3 scripts/model_usage_report.py

# Постоянный мониторинг
bash scripts/monitor_models.sh
```

### Результаты:
- `/tmp/available_models.json` - список доступных моделей
- `/tmp/model_usage_report.json` - подробный отчет об использовании

---

## 🔄 АВТОВЫБОР МОДЕЛЕЙ (НОВОЕ!)

**С 2026-01-30 внедрён автовыбор моделей:**

### Как работает:
1. При запуске сканируются **Ollama (порт 11434)** и **MLX (порт 11435)** РАЗДЕЛЬНО
2. Выбираются **самые мощные** из каждого списка
3. Если `VICTORIA_MODEL` / `VERONICA_MODEL` не заданы — используется автовыбор

### Приоритет Ollama (для executor/planner):
```
qwq:32b > qwen2.5-coder:32b > glm-4.7-flash:q8_0 > phi3.5:3.8b > tinyllama:1.1b-chat
```

### Приоритет MLX (для LocalAIRouter):
```
command-r-plus:104b > deepseek-r1-distill-llama:70b > llama3.3:70b > qwen2.5-coder:32b
```

### Конфигурация:
```yaml
# docker-compose.yml - автовыбор (рекомендуется)
VICTORIA_MODEL: ${VICTORIA_MODEL:-}        # Пустое = автовыбор
VERONICA_MODEL: ${VERONICA_MODEL:-}        # Пустое = автовыбор

# Или явное указание
VICTORIA_MODEL: qwen2.5-coder:32b          # Явно указать модель
```

---

## ⚠️ УСТАРЕВШИЕ МОДЕЛИ (удалены из кода)

- ❌ `deepseek-r1:7b` — не существует, заменено на автовыбор
- ❌ `qwen2.5-coder:7b` — не существует, заменено на автовыбор
- ❌ Все hardcoded модели заменены на автовыбор

---

**Обновление:** Система автоматически сканирует и выбирает лучшие доступные модели из Ollama и MLX раздельно.
