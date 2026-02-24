# Изменение приоритета: MLX API Server вместо Ollama

**Дата:** 26.01.2026  
**Изменение:** Чат теперь использует MLX API Server напрямую, а не через Ollama

---

## 🔄 Что изменилось

### Раньше:

1. Victoria (если доступна)
2. Ollama (основной)
3. MLX (fallback при ошибке Ollama)

### Теперь:

1. Victoria (если доступна)
2. **MLX API Server (приоритет)** ✅
3. Ollama (fallback при ошибке MLX)
4. Victoria (последний fallback)

---

## ✅ Изменения в коде

### 1. MLX Client (`backend/app/services/mlx.py`)

**Было:** Использовал `mlx_router` из knowledge_os (прямой импорт)

**Стало:** Использует MLX API Server через HTTP API на порту 11435

```python
# Теперь MLX Client подключается к MLX API Server через HTTP
MLX_API_URL = "http://localhost:11435"

async def generate(self, prompt, system, max_tokens, model):
    # HTTP запрос к /api/generate
    response = await client.post(f"{self.base_url}/api/generate", json=payload)
```

### 2. Chat Router (`backend/app/routers/chat.py`)

**Было:** Сначала Ollama, потом MLX как fallback

**Стало:** Сначала MLX API Server, потом Ollama как fallback

```python
# ПРИОРИТЕТ: Сначала пробуем MLX API Server
if mlx_available.get("status") == "healthy":
    result = await mlx.generate(...)

# Fallback на Ollama если MLX недоступен
if result is None or "error" in result:
    result = await ollama.generate(...)
```

---

## 🎯 Преимущества

1. **MLX API Server работает напрямую:**
   - Использует предзагруженные модели (быстрее)
   - Умное управление памятью
   - Защита от выгрузки активных моделей

2. **Лучшая производительность:**
   - Модели уже в памяти (предзагрузка)
   - Нет задержек на загрузку
   - Оптимизированное использование RAM

3. **Надежность:**
   - MLX API Server имеет мониторинг памяти
   - Автоматическая очистка неиспользуемых моделей
   - Защита от OOM ошибок

---

## 📊 Текущий статус

- ✅ MLX API Server: работает на порту 11435
- ✅ Моделей в кэше: 3 (qwen2.5-coder:32b, phi3.5:3.8b, tinyllama:1.1b-chat)
- ✅ Ollama: доступен как fallback

---

## 🔧 После изменений

**Перезапустите backend:**

```bash
# Остановить старый процесс
lsof -ti:8080 | xargs kill

# Запустить заново
cd backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🧪 Тестирование

После перезапуска:

1. Откройте чат в браузере
2. Отправьте сообщение
3. Проверьте логи backend - должно быть: `🍎 [MLX] Генерируем ответ через MLX API Server`

---

_Изменения применены: 26.01.2026_
