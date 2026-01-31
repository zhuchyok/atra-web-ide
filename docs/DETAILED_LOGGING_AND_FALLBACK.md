# Детальное логирование и автоматический Fallback

## Дата: 2026-01-30

## Проблема

При отправке запроса к Victoria через `chat_victoria.sh` возникала ошибка:
```
Connection reset by peer
```

Причина: модель `qwen2.5-coder:32b` падала с ошибкой "model runner has unexpectedly stopped" из-за нехватки ресурсов.

## Реализованные улучшения

### 1. Детальное логирование в executor.py

Добавлено логирование на всех этапах:

```
[EXECUTOR_INIT] - Инициализация executor с URL и моделями
[LLM_CALL] - Параметры каждого запроса к модели
[LLM_RESPONSE] - Статус ответа, время выполнения, контент
[LLM_ERROR] - Подробности ошибок
[LLM_PARSE] - Разбор ответа модели
[LLM_CRASH] - Детектирование падения модели
[FALLBACK] - Попытки переключения на другую модель
```

### 2. Автоматический Fallback при падении модели

Добавлена логика автоматического переключения на другую модель:

```python
# Порядок fallback моделей для Ollama
FALLBACK_MODELS_OLLAMA = [
    "phi3.5:3.8b",      # Fast, stable
    "tinyllama:1.1b-chat",  # Very small, always works
    "glm-4.7-flash:q8_0",   # Medium, good quality
    "qwen2.5-coder:32b",    # Large, may crash on limited RAM
]

# Порядок fallback моделей для MLX
FALLBACK_MODELS_MLX = [
    "phi3.5:3.8b",
    "qwen2.5:3b",
    "tinyllama:1.1b-chat",
    "phi3:mini-4k",
    "qwen2.5-coder:32b",
]
```

**Механизм fallback:**
- При получении HTTP 500 или ошибки с индикаторами краша ("unexpectedly stopped", "out of memory")
- Модель добавляется в `_failed_models` (не будет повторно использоваться в сессии)
- Ищется следующая доступная модель (сначала MLX, потом Ollama)
- Максимум 3 попытки fallback

### 3. Диагностический скрипт

Создан скрипт `scripts/test_request_flow.py`:

```bash
# Базовая проверка
python3 scripts/test_request_flow.py

# С подробным выводом
python3 scripts/test_request_flow.py --verbose

# Тест конкретной модели
python3 scripts/test_request_flow.py --model phi3.5:3.8b

# Использовать MLX вместо Ollama
python3 scripts/test_request_flow.py --use-mlx

# Свой запрос
python3 scripts/test_request_flow.py --goal "напиши код"
```

**Что проверяет скрипт:**
1. Подключение к Victoria, Ollama, MLX
2. Список доступных моделей
3. Прямой тест модели (без Victoria)
4. Полный цикл запроса через Victoria

## Результаты тестирования

### До изменений:
```
⚠️ Ошибка опроса: ('Connection aborted.', ConnectionResetError(54, 'Connection reset by peer'))
❌ Не удалось получить ответ от Victoria
```

### После изменений:
```
✅ Task completed! Total time: 12361ms
Model: Victoria Enhanced
```

## Логи показывают полный путь запроса

```
[REQUEST] ========== POST /run ==========
[REQUEST] Correlation ID: 25a0b2f7-...
[REQUEST] Goal: Создай простой polling бот для телеграм с aiogram
[REQUEST] Async mode: True
[REQUEST] Task type detected: enhanced
[LLM_CALL] Model: qwq:32b
[LLM_CALL] Is retry/fallback: False
[LLM_RESPONSE] ✅ Success!
```

## Использование

### Включение debug режима:

```bash
# В .env
VICTORIA_DEBUG=true

# Или через переменную окружения
VICTORIA_DEBUG=true python3 scripts/chat_victoria.sh

# Или в чате
/debug
```

### Отключение MLX fallback:

```bash
USE_MLX_FALLBACK=false
```

## Файлы изменений

- `src/agents/core/executor.py` - Добавлен fallback и детальное логирование
- `scripts/test_request_flow.py` - Новый диагностический скрипт

## Мониторинг

Для просмотра логов в реальном времени:

```bash
docker logs -f victoria-agent 2>&1 | grep -E "\[LLM_|REQUEST|FALLBACK"
```
