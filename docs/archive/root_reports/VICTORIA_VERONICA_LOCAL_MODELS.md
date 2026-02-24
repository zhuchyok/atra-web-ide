# ✅ VICTORIA И VERONICA - АВТОВЫБОР ЛОКАЛЬНЫХ МОДЕЛЕЙ

**Дата:** 2026-01-30  
**Статус:** ✅ **ДА, ОБА АГЕНТА ИСПОЛЬЗУЮТ ЛОКАЛЬНЫЕ МОДЕЛИ С АВТОВЫБОРОМ**

---

## 🎯 ОТВЕТ

**✅ ДА, и Victoria, и Veronica используют ВАШИ локальные модели!**

Оба агента настроены на **автоматический выбор лучшей доступной модели** из локального Ollama/MLX API.

---

## 🔄 НОВОЕ: АВТОВЫБОР МОДЕЛЕЙ

### Как работает:

1. При запуске сканируются **Ollama (порт 11434)** и **MLX (порт 11435)** **РАЗДЕЛЬНО**
2. Выбираются **самые мощные** из каждого списка
3. Списки не смешиваются — Ollama для executor/planner, MLX для LocalAIRouter

### Приоритет выбора Ollama:

```
qwq:32b → qwen2.5-coder:32b → glm-4.7-flash:q8_0 → phi3.5:3.8b → tinyllama:1.1b-chat
```

### Приоритет выбора MLX:

```
command-r-plus:104b → deepseek-r1-distill-llama:70b → llama3.3:70b → qwen2.5-coder:32b
```

---

## 📊 VICTORIA AGENT - КОНФИГУРАЦИЯ

### Автовыбор модели (рекомендуется):

```python
# src/agents/bridge/victoria_server.py

class VictoriaAgent(BaseAgent):
    def __init__(self, name: str = "Виктория", model_name: str = None):
        # Автовыбор модели: None = сканирование Ollama при первом запросе
        model_name = model_name or os.getenv("VICTORIA_MODEL") or None

        # При первом запросе:
        # 1. Сканируется Ollama (http://localhost:11434/api/tags)
        # 2. Выбирается лучшая модель по приоритету
        # 3. Используется для всех последующих запросов
```

### Результат сканирования:

```
🔵 OLLAMA МОДЕЛИ (для executor/planner):
   Доступно: 7
   Список: ['qwq:32b', 'qwen2.5-coder:32b', 'glm-4.7-flash:q8_0', ...]
   Лучшая: qwq:32b ✅

🟢 MLX МОДЕЛИ (для LocalAIRouter):
   Доступно: 15
   Список: ['command-r-plus:104b', 'deepseek-r1-distill-llama:70b', ...]
   Лучшая: command-r-plus:104b ✅
```

### Как работает Victoria:

```
Запрос → Автовыбор модели → LocalAIRouter → OllamaExecutor → Ollama/MLX API → Локальная модель
```

---

## 📊 VERONICA AGENT - КОНФИГУРАЦИЯ

### Автовыбор модели (рекомендуется):

```python
# src/agents/bridge/server.py

class VeronicaAgent(BaseAgent):
    def __init__(self, name: str = "Вероника", model_name: str = None):
        # Автовыбор модели: None = сканирование Ollama при первом запросе
        model_name = model_name or os.getenv("VERONICA_MODEL") or None

        # Planner и Executor с автовыбором
        self.planner = OllamaExecutor(model=planner_model, base_url=base)
        self.executor = OllamaExecutor(model=model_name, base_url=base)
```

### Как работает Veronica:

```
Запрос → Автовыбор модели → OllamaExecutor → Ollama/MLX API → Локальная модель
```

---

## 🔧 КОНФИГУРАЦИЯ

### Docker Compose (автовыбор):

```yaml
# knowledge_os/docker-compose.yml

victoria-agent:
  environment:
    OLLAMA_BASE_URL: http://host.docker.internal:11434
    MLX_API_URL: http://host.docker.internal:11435
    # Автовыбор модели (рекомендуется)
    VICTORIA_MODEL: ${VICTORIA_MODEL:-} # Пустое = автовыбор
    VICTORIA_PLANNER_MODEL: ${VICTORIA_PLANNER_MODEL:-}

veronica-agent:
  environment:
    OLLAMA_BASE_URL: http://host.docker.internal:11434
    # Автовыбор модели (рекомендуется)
    VERONICA_MODEL: ${VERONICA_MODEL:-} # Пустое = автовыбор
    VERONICA_PLANNER_MODEL: ${VERONICA_PLANNER_MODEL:-}
```

### Явное указание модели:

```yaml
# Если нужно зафиксировать конкретную модель:
VICTORIA_MODEL: qwen2.5-coder:32b
VERONICA_MODEL: phi3.5:3.8b
```

---

## 📋 СРАВНЕНИЕ МОДЕЛЕЙ

| Агент             | Executor              | Planner   | Источник | Автовыбор |
| ----------------- | --------------------- | --------- | -------- | --------- |
| **Victoria**      | `qwq:32b` (лучшая)    | `qwq:32b` | Ollama   | ✅ ДА     |
| **Veronica**      | `qwq:32b` (лучшая)    | `qwq:32b` | Ollama   | ✅ ДА     |
| **LocalAIRouter** | `command-r-plus:104b` | -         | MLX      | ✅ ДА     |

---

## ✅ ДОКАЗАТЕЛЬСТВА

### 1. Victoria использует автовыбор:

- ✅ При запуске сканируется Ollama и MLX
- ✅ Выбирается лучшая доступная модель
- ✅ Списки Ollama и MLX раздельные
- ✅ Нет hardcoded моделей

### 2. Veronica использует автовыбор:

- ✅ При первом запросе сканируется Ollama
- ✅ Выбирается лучшая доступная модель
- ✅ Нет hardcoded моделей

### 3. Логи подтверждают:

```
[MODEL_SELECT] СКАНИРОВАНИЕ МОДЕЛЕЙ (Ollama и MLX РАЗДЕЛЬНО)
[MODEL_SELECT] 🔵 OLLAMA МОДЕЛИ (для executor/planner):
[MODEL_SELECT]    Лучшая: qwq:32b
[MODEL_SELECT] 🟢 MLX МОДЕЛИ (для LocalAIRouter):
[MODEL_SELECT]    Лучшая: command-r-plus:104b
[MODEL_SELECT] ✅ МОДЕЛИ ВЫБРАНЫ:
[MODEL_SELECT]    Executor: qwq:32b
[MODEL_SELECT]    Planner: qwq:32b
```

---

## 🚫 ОБЛАЧНЫЕ МОДЕЛИ НЕ ИСПОЛЬЗУЮТСЯ

- ❌ Нет импортов `openai` или `anthropic` в коде агентов
- ❌ `OPENAI_API_KEY` закомментирован в `.env`
- ❌ `ANTHROPIC_API_KEY` закомментирован в `.env`
- ❌ Все запросы идут через `OllamaExecutor` → `localhost:11434`

---

## ✅ ИТОГ

**✅ ДА, и Victoria, и Veronica используют ВАШИ локальные модели с автовыбором!**

### Victoria:

- ✅ Автовыбор лучшей модели из Ollama
- ✅ LocalAIRouter для MLX поддержки
- ✅ URL: `localhost:11434` (Ollama) / `localhost:11435` (MLX)

### Veronica:

- ✅ Автовыбор лучшей модели из Ollama
- ✅ URL: `localhost:11434` (Ollama)

**Оба агента полностью работают на локальных моделях Mac Studio с автовыбором!** 🎉

---

_Обновлено: 2026-01-30_
