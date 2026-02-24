# Victoria и зависимость от Ollama

**Дата:** 2026-01-26

## ❓ Вопрос: Может ли Victoria работать без Ollama?

## 📊 Ответ: Частично

### Текущая архитектура:

Victoria использует **Ollama API** для работы с моделями:

1. **OllamaExecutor** (основной):
   - Использует `{base_url}/api/chat`
   - Требует Ollama API или совместимый API (MLX API Server)

2. **LocalAIRouter** (опциональный):
   - Может использовать MLX напрямую
   - Но в итоге тоже идет через API (Ollama-совместимый)

3. **Victoria Enhanced компоненты**:
   - Extended Thinking → требует Ollama API (`/api/generate`)
   - Swarm Intelligence → требует Ollama API
   - Consensus → требует Ollama API
   - И другие...

### ✅ Альтернативы Ollama:

#### 1. MLX API Server (рекомендуется)

- ✅ Эмулирует Ollama API
- ✅ Работает без изменений кода
- ✅ Использует MLX модели (быстрее на Apple Silicon)
- ✅ URL: `http://localhost:11434` (тот же порт)

**Настройка:**

```bash
# Запустить MLX API Server вместо Ollama
bash scripts/start_mlx_api_server.sh
```

#### 2. Другие Ollama-совместимые API

- Любой сервер, который эмулирует Ollama API
- Должен поддерживать `/api/chat` и `/api/generate`

### ❌ Без API сервера:

Victoria **НЕ МОЖЕТ** работать полностью без API сервера, потому что:

1. **OllamaExecutor** всегда использует HTTP API:

   ```python
   url = f"{self.base_url}/api/chat"  # Требует API сервер
   ```

2. **Victoria Enhanced** компоненты требуют API:
   - Extended Thinking → `/api/generate`
   - Все остальные → `/api/chat`

3. **LocalAIRouter** тоже использует API:
   - Может использовать MLX напрямую, но через API endpoint

### 💡 Решение:

**Используйте MLX API Server вместо Ollama:**

- ✅ Совместимый API (работает без изменений)
- ✅ Быстрее на Mac Studio
- ✅ Использует MLX модели
- ✅ Тот же порт (11434)

**Или оставьте Ollama:**

- ✅ Работает "из коробки"
- ✅ Поддерживает все модели
- ✅ Уже настроена и работает

---

**Вывод:** Victoria требует API сервер (Ollama или совместимый), но может работать с MLX API Server вместо Ollama.
