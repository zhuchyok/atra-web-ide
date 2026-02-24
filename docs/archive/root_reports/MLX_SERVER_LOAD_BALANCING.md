# ⚖️ Разгрузка MLX API Server: Как это работает

**Дата:** 2026-01-26  
**Важно:** Claude Code + MLX = **ДОПОЛНИТЕЛЬНАЯ нагрузка**, не разгрузка!

---

## ❌ Миф: Claude Code разгружает MLX сервер

**НЕТ!** Claude Code **добавляет нагрузку** на MLX API Server, потому что:

- Claude Code делает запросы к MLX API Server
- Каждый запрос от Claude Code = нагрузка на MLX
- Это **дополнительный клиент**, а не разгрузка

---

## ✅ Как НА САМОМ ДЕЛЕ разгрузить MLX сервер

### 1. **Использовать Ollama для простых задач**

**Стратегия:**

- Простые задачи → Ollama (порт 11434)
- Сложные задачи → MLX (порт 11435)

**Как это работает:**

```python
# Victoria автоматически выбирает:
if task_is_simple:
    use_ollama()  # Разгружает MLX
else:
    use_mlx()     # Использует MLX для сложных задач
```

**Реализовано в:**

- `LocalAIRouter` - автоматический выбор между MLX и Ollama
- `ModelSelector` - выбор модели на основе сложности задачи

---

### 2. **Использовать Cloud модели для очень сложных задач**

**Стратегия:**

- Очень сложные задачи → Ollama Cloud (gpt-oss:120b-cloud)
- Это разгружает **и MLX, и локальный Ollama**

**Как использовать:**

```python
# Для очень сложных задач
client = OllamaClient(use_cloud=True)
result = await client.generate(
    prompt="Очень сложная задача",
    model="gpt-oss:120b-cloud"  # Cloud модель
)
```

---

### 3. **Очередь запросов с приоритетами**

**Уже реализовано!** ✅

**Как работает:**

- **HIGH приоритет** - Чат с Викторией (обрабатывается первым)
- **MEDIUM приоритет** - Task Distribution (может подождать)
- **LOW приоритет** - Фоновые задачи (обрабатываются последними)

**Настройка:**

```python
# Victoria использует HIGH приоритет
headers = {"X-Request-Priority": "high"}

# Task Distribution использует MEDIUM
headers = {"X-Request-Priority": "medium"}

# Фоновые задачи используют LOW
headers = {"X-Request-Priority": "low"}
```

**Файл:** `knowledge_os/app/mlx_request_queue.py`

---

### 4. **Rate Limiting (Ограничение частоты запросов)**

**Уже реализовано!** ✅

**Параметры:**

- Максимум **30 запросов в минуту** на IP
- Максимум **5 параллельных запросов** одновременно

**Как работает:**

```python
# В mlx_api_server.py
_rate_limit_max = 30  # запросов
_rate_limit_window = 60  # секунд
_max_concurrent_requests = 5  # параллельных
```

**Если превышен лимит:**

- Запрос отклоняется с ошибкой 429 (Too Many Requests)
- Защита от перегрузки сервера

---

### 5. **Автоматический Fallback на Ollama**

**Уже реализовано!** ✅

**Как работает:**

1. Пробует MLX API Server (порт 11435)
2. Если MLX недоступен → пробует Ollama (порт 11434)
3. Если Ollama недоступен → пробует Cloud

**Реализовано в:**

- `LocalAIRouter` - автоматический fallback
- `ModelSelector` - выбор доступной модели
- `ReActAgent` - fallback между источниками

---

### 6. **Автоматическая очистка памяти**

**Уже реализовано!** ✅

**Как работает:**

- При использовании памяти > 85% → предупреждение
- При использовании памяти > 95% → экстренная очистка
- Выгружает неиспользуемые модели (LRU стратегия)

**Параметры:**

```python
_memory_warning_threshold = 0.85  # 85%
_memory_critical_threshold = 0.95  # 95%
```

---

## 📊 Текущие механизмы защиты

### 1. **Очередь запросов**

- ✅ Приоритеты (HIGH/MEDIUM/LOW)
- ✅ Максимум 5 параллельных запросов
- ✅ Максимум 50 запросов в очереди

### 2. **Rate Limiting**

- ✅ 30 запросов в минуту на IP
- ✅ Защита от DDoS

### 3. **Автоматический Fallback**

- ✅ MLX → Ollama → Cloud
- ✅ Разгружает MLX при перегрузке

### 4. **Управление памятью**

- ✅ Автоматическая очистка неиспользуемых моделей
- ✅ Защита от OOM (Out of Memory)

---

## 🎯 Рекомендации по разгрузке

### Для Victoria (Telegram/Web):

```python
# Используйте HIGH приоритет
headers = {"X-Request-Priority": "high"}
# Victoria получает ответ быстрее
```

### Для Task Distribution:

```python
# Используйте MEDIUM приоритет
headers = {"X-Request-Priority": "medium"}
# Может подождать, не блокирует чат
```

### Для Claude Code:

```python
# Используйте LOW приоритет (если возможно)
# Или используйте Ollama вместо MLX:
export ANTHROPIC_BASE_URL=http://localhost:11434  # Ollama
# Это разгрузит MLX сервер!
```

---

## 💡 Оптимальная стратегия разгрузки

### Сценарий 1: MLX перегружен

**Решение:**

```bash
# Настроить Claude Code на Ollama
export ANTHROPIC_BASE_URL=http://localhost:11434  # Ollama вместо MLX!
claude --model qwen3-coder
```

**Результат:**

- ✅ Claude Code использует Ollama
- ✅ MLX разгружен для Victoria
- ✅ Victoria получает ответы быстрее

### Сценарий 2: Оба сервера перегружены

**Решение:**

```bash
# Использовать Cloud модели
export OLLAMA_API_KEY=your_key
export ANTHROPIC_BASE_URL=https://ollama.com  # Cloud!
claude --model gpt-oss:120b-cloud
```

**Результат:**

- ✅ Разгружает и MLX, и локальный Ollama
- ✅ Использует облачные ресурсы

### Сценарий 3: Нормальная нагрузка

**Решение:**

```bash
# Использовать MLX (быстрее на Mac Studio)
export ANTHROPIC_BASE_URL=http://localhost:11435  # MLX
claude --model qwen2.5-coder:32b
```

**Результат:**

- ✅ Использует MLX (быстрее)
- ✅ Очередь с приоритетами управляет нагрузкой

---

## 📈 Мониторинг нагрузки

### Проверить статистику очереди:

```bash
curl http://localhost:11435/queue/stats
```

**Ответ:**

```json
{
  "active_requests": 2,
  "max_concurrent": 5,
  "queue_size": 3,
  "stats": {
    "total_queued": 100,
    "total_processed": 97,
    "by_priority": {
      "HIGH": 50,
      "MEDIUM": 40,
      "LOW": 10
    }
  }
}
```

### Проверить health:

```bash
curl http://localhost:11435/health
```

**Ответ показывает:**

- Использование памяти
- Активные запросы
- Загруженные модели
- Предупреждения

---

## ✅ Итого: Как разгрузить MLX сервер

### ✅ РАЗГРУЖАЕТ:

1. **Использовать Ollama для простых задач** - автоматически через LocalAIRouter
2. **Использовать Cloud модели** - для очень сложных задач
3. **Очередь с приоритетами** - уже работает
4. **Rate Limiting** - защита от перегрузки
5. **Автоматический Fallback** - на Ollama при перегрузке MLX

### ❌ НЕ РАЗГРУЖАЕТ:

1. **Claude Code + MLX** - добавляет нагрузку (дополнительный клиент)
2. **Больше запросов** - увеличивает нагрузку

### 💡 Оптимальная стратегия:

- **Victoria (Telegram/Web)** → MLX с HIGH приоритетом
- **Claude Code** → Ollama (разгружает MLX)
- **Сложные задачи** → Cloud модели
- **Простые задачи** → Ollama

**Результат:** MLX используется для критичных задач (Victoria), а простые задачи идут через Ollama! 🚀
