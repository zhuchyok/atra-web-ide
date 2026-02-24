# 💻 Claude Code + MLX: Поддержка MLX моделей

**Дата:** 2026-01-26  
**Статус:** ✅ **ДОБАВЛЕНО**

---

## 🎯 Проблема

**Claude Code работает только с Ollama моделями**, потому что:

- Claude Code использует **Anthropic-compatible API** (`/v1/messages`)
- Ollama эмулирует Anthropic API
- MLX API Server эмулировал только **Ollama API** (`/api/generate`)

**Результат:** Claude Code не мог использовать MLX модели напрямую.

---

## ✅ Решение

Добавлена поддержка **Anthropic-compatible API** в MLX API Server!

### Что добавлено:

1. **Endpoint `/v1/messages`** - Anthropic-compatible API
2. **Поддержка streaming** - для интерактивной работы
3. **Автоматический маппинг моделей** - из Anthropic имен в MLX

---

## 🚀 Как использовать

### Шаг 1: Запустить MLX API Server

```bash
# Запустить MLX API Server на порту 11435
cd /Users/bikos/Documents/atra-web-ide
python3 -m uvicorn knowledge_os.app.mlx_api_server:app --host 0.0.0.0 --port 11435
```

### Шаг 2: Настроить Claude Code для MLX

```bash
# Установить переменные окружения
export ANTHROPIC_AUTH_TOKEN=ollama
export ANTHROPIC_API_KEY=""
export ANTHROPIC_BASE_URL=http://localhost:11435  # MLX API Server вместо Ollama!
```

### Шаг 3: Запустить Claude Code

```bash
cd /Users/bikos/Documents/atra-web-ide
claude --model qwen2.5-coder:32b  # MLX модель!
```

---

## 📊 Сравнение

| Параметр        | Ollama        | MLX API Server                  |
| --------------- | ------------- | ------------------------------- |
| **Скорость**    | Средняя       | ⚡ Быстрее (Neural Engine)      |
| **Память**      | Больше        | 💾 Меньше (квантованные модели) |
| **Claude Code** | ✅ Работает   | ✅ **Теперь работает!**         |
| **Модели**      | Ollama модели | MLX модели (наши локальные)     |

---

## 🔧 Технические детали

### Endpoint: `/v1/messages`

**Формат запроса (Anthropic):**

```json
{
  "model": "qwen2.5-coder:32b",
  "messages": [{ "role": "user", "content": "Привет!" }],
  "max_tokens": 1024
}
```

**Что происходит:**

1. MLX API Server получает Anthropic-формат запрос
2. Преобразует в Ollama формат (объединяет сообщения)
3. Использует существующую логику генерации MLX
4. Возвращает ответ в Anthropic формате

### Streaming поддержка

Claude Code может использовать streaming для интерактивной работы:

- Формат: Server-Sent Events (SSE)
- Типы событий: `content_block_delta`, `message_delta`, `message_stop`

---

## 🎯 Преимущества

### 1. **Используем наши MLX модели**

- ✅ Быстрее на Apple Silicon
- ✅ Экономия памяти
- ✅ Наши локальные модели

### 2. **Claude Code работает с MLX**

- ✅ Прямой доступ к MLX моделям
- ✅ Не нужен Ollama как промежуточный слой
- ✅ Полная интеграция

### 3. **Единый API сервер**

- ✅ MLX API Server поддерживает и Ollama API, и Anthropic API
- ✅ Один сервер для всех клиентов
- ✅ Упрощенная архитектура

---

## 📝 Примеры использования

### Пример 1: Базовое использование

```bash
# Настроить Claude Code
export ANTHROPIC_BASE_URL=http://localhost:11435
claude --model qwen2.5-coder:32b

# В Claude Code:
"Проанализируй victoria_telegram_bot.py"
→ Использует MLX модель qwen2.5-coder:32b!
```

### Пример 2: С Cloud моделями

```bash
# Если хотите использовать Cloud модели через Ollama
export ANTHROPIC_BASE_URL=http://localhost:11434  # Ollama
claude --model gpt-oss:120b-cloud
```

### Пример 3: Через Python

```python
import anthropic

client = anthropic.Anthropic(
    base_url='http://localhost:11435',  # MLX API Server
    api_key='ollama'  # Требуется, но игнорируется
)

message = client.messages.create(
    model='qwen2.5-coder:32b',  # MLX модель
    max_tokens=1024,
    messages=[{
        'role': 'user',
        'content': 'Привет!'
    }]
)
```

---

## ⚠️ Важные замечания

### 1. Порт MLX API Server

- По умолчанию: `11435`
- Ollama использует: `11434`
- Claude Code должен указывать правильный порт

### 2. Маппинг моделей

- MLX API Server автоматически маппит имена моделей
- Если модель не найдена, вернется ошибка 404

### 3. Streaming

- MLX не поддерживает настоящий streaming
- Эмулируется через разбиение ответа на символы
- Для Claude Code это прозрачно

### 4. ⚠️ Нагрузка на MLX сервер

**ВАЖНО:** Claude Code + MLX = **ДОПОЛНИТЕЛЬНАЯ нагрузка** на MLX сервер!

**Для разгрузки MLX:**

- Используйте Ollama для Claude Code: `export ANTHROPIC_BASE_URL=http://localhost:11434`
- Это разгрузит MLX для Victoria (Telegram/Web)
- MLX будет использоваться только для критичных задач

**Подробнее:** См. `MLX_SERVER_LOAD_BALANCING.md`

---

## 🔄 Миграция с Ollama на MLX

### Было (Ollama):

```bash
export ANTHROPIC_BASE_URL=http://localhost:11434
claude --model qwen3-coder
```

### Стало (MLX):

```bash
export ANTHROPIC_BASE_URL=http://localhost:11435  # MLX!
claude --model qwen2.5-coder:32b  # MLX модель!
```

---

## ✅ Итого

**Теперь Claude Code может работать с MLX моделями!**

1. ✅ Добавлен endpoint `/v1/messages` в MLX API Server
2. ✅ Поддержка Anthropic-compatible API
3. ✅ Streaming поддержка
4. ✅ Автоматический маппинг моделей
5. ✅ Использование наших локальных MLX моделей

**Результат:** Claude Code работает быстрее и использует наши оптимизированные MLX модели! 🚀
