# ☁️ Ollama Cloud & Claude Code Integration

**Дата:** 2026-01-26  
**Статус:** ✅ **ДОБАВЛЕНО**

---

## 🎯 Обзор

Добавлена поддержка:
- ✅ **Ollama Cloud Models** - облачные модели без локального GPU
- ✅ **Claude Code Integration** - интеграция с Claude Code через Anthropic-compatible API

---

## ☁️ Ollama Cloud Models

### Что это?

Ollama Cloud Models - это модели, которые работают в облаке Ollama без необходимости локального GPU. Они автоматически оффлоудятся в облачный сервис Ollama, предлагая те же возможности, что и локальные модели.

### Поддерживаемые Cloud модели

- `gpt-oss:120b-cloud` - 120B параметров (очень мощная)
- `gpt-oss:20b-cloud` - 20B параметров (средняя мощность)
- `qwen3-coder-cloud` - Coding модель
- `glm-4.7-cloud` - Reasoning модель

### Использование

#### 1. Получить API ключ

1. Зарегистрируйтесь на [ollama.com](https://ollama.com)
2. Создайте API ключ в [настройках](https://ollama.com/settings/keys)
3. Установите переменную окружения:

```bash
export OLLAMA_API_KEY=your_api_key_here
```

#### 2. Использование в коде

```python
from backend.app.services.ollama import OllamaClient

# Создание клиента с Cloud API
client = OllamaClient(use_cloud=True)

# Использование Cloud модели
result = await client.generate(
    prompt="Сложная задача",
    model="gpt-oss:120b-cloud"
)
```

#### 3. Загрузка Cloud модели

```python
# Загрузить Cloud модель
await client.pull_model("gpt-oss:120b-cloud")
```

---

## 💻 Claude Code Integration

### Что это?

Claude Code - это агентный инструмент для кодирования от Anthropic, который может читать, модифицировать и выполнять код в рабочей директории. Теперь можно использовать открытые модели через Ollama с Claude Code.

### Рекомендованные модели

- `qwen3-coder` - Специализированная coding модель
- `glm-4.7` - Мощная reasoning модель
- `gpt-oss:20b` - Баланс качества и скорости
- `gpt-oss:120b` - Максимальное качество (Cloud)

### Быстрая настройка

#### Вариант 1: Автоматическая настройка

```bash
ollama launch claude
```

Это автоматически настроит Claude Code для работы с Ollama.

#### Вариант 2: Ручная настройка

```bash
# Установить переменные окружения
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:11434

# Запустить Claude Code с моделью
claude --model qwen3-coder
```

#### Вариант 3: Через Python

```python
from backend.app.services.ollama import OllamaClient

client = OllamaClient()
config = client.get_anthropic_compatible_config()

# Использовать config для настройки Claude Code
# config содержит:
# {
#     "ANTHROPIC_AUTH_TOKEN": "ollama",
#     "ANTHROPIC_API_KEY": "",
#     "ANTHROPIC_BASE_URL": "http://localhost:11434"
# }
```

### Требования

- **Claude Code установлен**: `curl -fsSL https://claude.ai/install.sh | bash`
- **Ollama запущен** локально или Cloud API настроен
- **Модель с большим контекстом** (минимум 64k токенов)

### Использование

После настройки Claude Code будет работать с выбранной моделью Ollama, позволяя:
- Читать код из рабочей директории
- Модифицировать код
- Выполнять код
- Анализировать проекты

---

## 🔧 Интеграция в проект

### Обновленный OllamaClient

```python
from backend.app.services.ollama import OllamaClient

# Локальный Ollama
local_client = OllamaClient()

# Cloud Ollama
cloud_client = OllamaClient(use_cloud=True)

# Получить конфигурацию для Claude Code
config = local_client.get_anthropic_compatible_config()
```

### Новые методы

1. **`pull_model(model_name)`** - Загрузить модель из Ollama
2. **`get_anthropic_compatible_config()`** - Получить конфигурацию для Claude Code

### Переменные окружения

- `OLLAMA_API_KEY` - API ключ для Ollama Cloud
- `OLLAMA_URL` - URL локального Ollama (по умолчанию `http://localhost:11434`)

---

## 📊 Навыки

Созданы два новых навыка:

1. **ollama-cloud** - Использование Cloud моделей
2. **claude-code-integration** - Интеграция с Claude Code

---

## 🚀 Примеры использования

### Пример 1: Использование Cloud модели

```python
from backend.app.services.ollama import OllamaClient

client = OllamaClient(use_cloud=True)
result = await client.generate(
    prompt="Создай REST API для управления пользователями",
    model="gpt-oss:120b-cloud"
)
```

### Пример 2: Настройка Claude Code

```bash
# Установить переменные окружения
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:11434

# Запустить Claude Code
claude --model qwen3-coder
```

---

## 📚 Источники

- [Ollama Cloud Documentation](https://docs.ollama.com/cloud)
- [Claude Code Integration](https://docs.ollama.com/integrations/claude-code)
- Файлы: `backend/app/services/ollama.py`