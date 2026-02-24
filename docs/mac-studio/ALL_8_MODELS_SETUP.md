# ✅ Настройка всех 8 моделей Mac Studio для чата

**Дата:** 2026-01-25  
**Статус:** ✅ Код обновлен для использования всех 8 моделей

---

## 📋 СПИСОК ВСЕХ 8 МОДЕЛЕЙ

| Модель                            | Размер | Назначение                                  | Автовыбор                   |
| --------------------------------- | ------ | ------------------------------------------- | --------------------------- |
| **command-r-plus:104b**           | ~65GB  | Максимальная мощность, RAG, мультиязычность | ✅ complex, enterprise      |
| **deepseek-r1-distill-llama:70b** | ~40GB  | Reasoning, планирование (distilled)         | ✅ reasoning                |
| **llama3.3:70b**                  | ~40GB  | Максимальное качество, общие задачи         | ✅ complex                  |
| **qwen2.5-coder:32b**             | ~20GB  | Качественный код, рефакторинг               | ✅ coding (high quality)    |
| **phi3.5:3.8b**                   | ~2.5GB | Быстрые задачи, общие                       | ✅ fast, general            |
| **phi3:mini-4k**                  | ~2GB   | Быстрые ответы, легкие задачи               | ✅ fast (lightweight)       |
| **qwen2.5:3b**                    | ~2GB   | Быстрые ответы, общие задачи                | ✅ fast, default            |
| **tinyllama:1.1b-chat**           | ~700MB | Очень быстрые ответы                        | ✅ fast (ultra-lightweight) |

---

## ✅ ЧТО СДЕЛАНО

### 1. Обновлена функция выбора моделей

**Файл:** `backend/app/routers/chat.py`

Функция `_select_model_for_chat()` теперь использует все 8 моделей:

- **complex/enterprise** → `command-r-plus:104b`
- **reasoning** → `deepseek-r1-distill-llama:70b`
- **complex** → `llama3.3:70b`
- **coding (high quality)** → `qwen2.5-coder:32b`
- **fast/general** → `phi3.5:3.8b`
- **fast (lightweight)** → `phi3:mini-4k`
- **fast/default** → `qwen2.5:3b`
- **fast (ultra-lightweight)** → `tinyllama:1.1b-chat`

### 2. Логика автоматического выбора

Система автоматически выбирает модель на основе:

- Содержания сообщения (ключевые слова)
- Длины сообщения
- Категории задачи (complex, reasoning, coding, fast)

---

## 🔍 ПРОВЕРКА УСТАНОВЛЕННЫХ МОДЕЛЕЙ

Проверить, какие модели установлены:

```bash
curl -s http://localhost:11434/api/tags | python3 -c "
import sys, json
data = json.load(sys.stdin)
models = [m.get('name') for m in data.get('models', [])]
print(f'Всего моделей: {len(models)}')
for m in sorted(models):
    print(f'  - {m}')
"
```

---

## 📝 УСТАНОВКА НЕДОСТАЮЩИХ МОДЕЛЕЙ

Если какая-то модель отсутствует, установить через Ollama:

```bash
# Маленькие модели (быстро)
ollama pull tinyllama:1.1b-chat
ollama pull qwen2.5:3b
ollama pull phi3:mini-4k
ollama pull phi3.5:3.8b

# Средние модели (займет время)
ollama pull qwen2.5-coder:32b

# Большие модели (очень долго, много места)
ollama pull llama3.3:70b
ollama pull deepseek-r1-distill-llama:70b
ollama pull command-r-plus:104b
```

---

## 🎯 ИСПОЛЬЗОВАНИЕ

Чат автоматически выбирает модель на основе запроса:

- **"Сложная корпоративная задача"** → `command-r-plus:104b`
- **"Подумай и объясни логику"** → `deepseek-r1-distill-llama:70b`
- **"Напиши качественный код"** → `qwen2.5-coder:32b`
- **"Быстрый ответ"** → `phi3:mini-4k` или `tinyllama:1.1b-chat`

---

## ✅ СТАТУС

- ✅ Код обновлен для использования всех 8 моделей
- ✅ Автоматический выбор настроен
- ⚠️ Требуется проверить наличие всех моделей в Ollama
- ⚠️ Требуется настроить Ollama для работы из Docker (OLLAMA_HOST=0.0.0.0:11434)
