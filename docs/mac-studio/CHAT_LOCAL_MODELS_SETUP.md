# 🔧 Настройка локальных моделей Mac Studio для чата

**Дата:** 2026-01-25  
**Статус:** ⚠️ Требуется настройка Ollama

---

## ✅ ЧТО СДЕЛАНО

### 1. Обновлен список моделей в коде

**Файл:** `backend/app/services/ollama.py`

Добавлен правильный список моделей Mac Studio M4 Max:

- `command-r-plus:104b` (~65GB) - Максимальная мощность
- `deepseek-r1-distill-llama:70b` (~40GB) - Reasoning
- `llama3.3:70b` (~40GB) - Максимальное качество
- `qwen2.5-coder:32b` (~20GB) - Качественный код
- `phi3.5:3.8b` (~2.5GB) - Быстрые задачи
- `phi3:mini-4k` (~2GB) - Быстрые ответы
- `qwen2.5:3b` (~2GB) - По умолчанию
- `tinyllama:1.1b-chat` (~700MB) - Очень быстрые

### 2. Автоматический выбор моделей

**Файл:** `backend/app/routers/chat.py`

Добавлена функция `_select_model_for_chat()`:

- Автоматически выбирает модель на основе содержания сообщения
- Использует доступные модели из реального списка
- Приоритет: coding → reasoning → fast → default

### 3. Конфигурация Docker

**Файл:** `docker-compose.yml`

Настроено:

- `OLLAMA_URL=http://host.docker.internal:11434`

---

## ❌ ПРОБЛЕМА

Из Docker контейнера не получается подключиться к Ollama на хосте:

- Ollama возвращает `404 Not Found` для `/api/generate`
- Возможно, Ollama слушает только на `localhost:11434`, а не на всех интерфейсах

---

## 🔧 РЕШЕНИЕ

### Вариант 1: Настроить Ollama слушать на всех интерфейсах

```bash
# Установить переменную окружения
export OLLAMA_HOST=0.0.0.0:11434

# Перезапустить Ollama
brew services restart ollama
# или
killall ollama && ollama serve
```

### Вариант 2: Использовать IP адрес напрямую

В `docker-compose.yml`:

```yaml
environment:
  - OLLAMA_URL=http://192.168.1.38:11434 # IP вашего Mac
```

### Вариант 3: Запустить backend не в Docker

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

---

## 📋 ДОСТУПНЫЕ МОДЕЛИ НА MAC STUDIO

Текущие модели в Ollama:

- `moondream:latest` - Vision
- `phi4:latest` - Fast/Balanced
- `deepseek-r1:7b` - Reasoning
- `qwen2.5-coder:3b` - Fast coding
- `qwen2.5-coder:7b` - Coding
- `nomic-embed-text:latest` - Embeddings

**Примечание:** Большие модели (command-r-plus:104b, deepseek-r1-distill-llama:70b, llama3.3:70b, qwen2.5-coder:32b) нужно установить отдельно через Ollama.

---

## ✅ ПРОВЕРКА

После настройки проверить:

```bash
# 1. Проверить, что Ollama слушает на всех интерфейсах
lsof -i :11434
# Должно быть: *:11434 (LISTEN), а не localhost:11434

# 2. Проверить подключение из Docker
docker exec atra-web-ide-backend python3 -c "
import httpx
import asyncio
async def test():
    client = httpx.AsyncClient(timeout=5.0)
    try:
        r = await client.get('http://host.docker.internal:11434/api/tags')
        print(f'✅ Подключение успешно: {r.status_code}')
    except Exception as e:
        print(f'❌ Ошибка: {e}')
asyncio.run(test())
"

# 3. Тест чата
curl -X POST http://localhost:8080/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"content":"Привет","expert_name":"Виктория","use_victoria":false}'
```

---

## 📝 ИТОГ

- ✅ Код обновлен с правильными моделями
- ✅ Автоматический выбор моделей настроен
- ⚠️ Требуется настройка Ollama для доступа из Docker

После настройки Ollama чат будет использовать локальные модели Mac Studio автоматически!
