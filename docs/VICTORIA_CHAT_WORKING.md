# ✅ Чат с Victoria — рабочий вариант

**Дата:** 2026-01-29  
**Тест:** `scripts/test_victoria_chat_works.py` (проходит при выполнении шагов ниже)

---

## Как запустить чат с Victoria (и чтобы она отвечала по существу)

### 1. Запустить Ollama или MLX API Server (хотя бы один)

**Ollama (порт 11434):**
```bash
# Если установлен через brew:
brew services start ollama
# или просто запустить в фоне:
ollama serve
# Убедиться, что есть модель, например:
ollama pull phi3.5:3.8b
```

**MLX API Server (порт 11435):**
```bash
cd ~/Documents/atra-web-ide
bash scripts/start_mlx_api_server.sh
# (в отдельном терминале, в фоне)
```

### 2. Запустить Victoria (Docker)

```bash
cd ~/Documents/atra-web-ide
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
# Подождать 15–20 секунд, пока контейнер поднимется
```

### 3. Открыть чат

```bash
bash scripts/chat_victoria.sh
# или
python3 scripts/victoria_chat.py
```

Напишите, например, «привет» или «кто ты?» — ответ должен приходить от модели (Ollama или MLX), а не шаблонный.

### 4. Проверить, что всё работает

```bash
python3 scripts/test_victoria_chat_works.py
# Должно вывести: OK: Victoria вернула настоящий ответ: ...
# и exit code 0
```

---

## Сканирование моделей при запросе

При обработке запроса (simple-метод) Victoria:

1. **Сканирует доступные модели** в MLX (порт 11435) и Ollama (11434): запросы к `/api/tags`, результат кэшируется на **2 минуты** (TTL), чтобы не дергать сервисы на каждый запрос.
2. **Выбирает провайдер и модель** в зависимости от категории запроса (fast, general, coding и т.д.):
   - **MLX:** передаётся `category` (fast/coding/default), MLX сам выбирает свою модель.
   - **Ollama:** из отсканированного списка выбирается первая подходящая по приоритету для категории (например fast → phi3.5:3.8b, tinyllama; general → qwen2.5-coder:32b и т.д.). Если в Ollama добавили или удалили модели — при следующем запросе (после истечения кэша) список обновится.

Модуль: `knowledge_os/app/available_models_scanner.py` — функции `get_available_models()`, `pick_ollama_model_for_category()`.

---

## Контекст чата (история диалога)

Скрипт чата передаёт в Victoria **последние 30 пар сообщений** (`chat_history`) в каждом запросе — то есть вся сессия, пока чат не закрыт. Victoria Enhanced подставляет эту историю в промпт модели:

```
Контекст предыдущих сообщений в чате:
Пользователь: ...
Victoria: ...
---
Текущий запрос пользователя: ...
```

История хранится в скрипте чата **до 100 пар** (вся сессия до выхода); в каждый запрос уходят последние **30 пар**, чтобы контекст не переполнял лимит модели.

---

## Что было исправлено (2026-01-29)

1. **MLX:** для MLX API Server в запросе передаётся `category` (fast/coding/default), а не имя модели в стиле Ollama — иначе MLX возвращал 500.
2. **Ollama:** для Ollama всегда используется маппинг категория → модель (`fast` → `phi3.5:3.8b`, `general` → `qwen2.5-coder:32b` и т.д.). Раньше подставлялся `selected_model` из MLX-селектора (например `deepseek-r1-distill-llama:70b`), которого нет в Ollama — получали 404.
3. **Fallback:** при недоступности обеих моделей возвращается понятное сообщение с подсказкой проверить порты 11435 и 11434.
4. **Тест:** добавлен `scripts/test_victoria_chat_works.py` — проверяет, что Victoria возвращает не шаблон, а ответ от модели.

---

## Порты

| Сервис           | Порт  | Назначение                          |
|------------------|-------|-------------------------------------|
| Victoria         | 8010  | Чат и /run                          |
| Ollama           | 11434 | LLM (fallback для simple-метода)   |
| MLX API Server   | 11435 | LLM (приоритет для simple-метода)  |

Из контейнера Victoria обращается к хосту по `host.docker.internal:11434` и `host.docker.internal:11435`.

---

## Если ответ всё ещё шаблонный

1. Перезапустить Victoria:  
   `docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent`
2. Убедиться, что на хосте отвечает хотя бы один из сервисов:  
   `curl -s http://localhost:11434/api/tags` или `curl -s http://localhost:11435/`
3. Запустить тест:  
   `python3 scripts/test_victoria_chat_works.py`
