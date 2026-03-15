# Виктория: Быстрый старт 🚀

Краткая шпаргалка для работы с Victoria во всех режимах.

---

## 1️⃣ Cursor (в IDE)

### Запуск

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
# MCP сервер запустится автоматически при старте Cursor
```

### Команды в чате

```
"Вызови Викторию: проанализируй структуру backend"
"Спроси Викторию: какие эксперты в команде?"
"Проверь victoria_health"
```

### Явный вызов

```
@VictoriaATRA victoria_run goal="Проверь тесты"
@VictoriaATRA victoria_chat message="Привет!"
```

---

## 2️⃣ Терминал чат

### Запуск

```bash
bash scripts/chat_victoria.sh
```

### Диалог

```
Victoria > Привет, Виктория!
✨ Victoria: Привет! Чем могу помочь?

Victoria > Проверь статус backend
✨ Victoria: ✅ Backend работает на порту 8080
```

### Удалённая Victoria

```bash
VICTORIA_REMOTE_URL=http://192.168.1.100:8010 bash scripts/chat_victoria.sh
```

---

## 3️⃣ Терминал команда

### Одна команда

```bash
python3 scripts/victoria_chat_standalone.py "Проверь статус"
```

### С контекстом проекта

```bash
PROJECT_CONTEXT=setki-21 python3 scripts/victoria_chat_standalone.py "Статус БД"
```

### В скрипте

```bash
RESPONSE=$(python3 scripts/victoria_chat_standalone.py "Health check")
echo "$RESPONSE"
```

---

## 4️⃣ Open WebUI

### Настройка (один раз)

1. Импорт инструмента: `configs/openwebui_ask_victoria_tool.py`
2. Valves → `VICTORIA_URL`: `http://victoria-agent:8000`
3. Загрузить документы: `MASTER_REFERENCE.md`, `COGNITIVE_CODE.md`
4. Системный промпт: `docs/SINGULARITY_15_GOLDEN_PERSONA.md`

### Использование

Просто пишите в чат — модель автоматически вызовет `ask_victoria`

### API

```bash
curl -X POST http://localhost:8080/api/chat/ask-victoria \
  -H "Content-Type: application/json" \
  -d '{"goal": "Статус backend", "project_context": "atra-web-ide"}'
```

---

## 5️⃣ Telegram

### Запуск

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-telegram-bot
```

### Использование

1. Найти бота: `@YourVictoriaBotName`
2. `/start`
3. Писать вопросы текстом

---

## 🔧 Быстрая диагностика

### Victoria не отвечает

```bash
curl http://localhost:8010/health
docker logs victoria-agent
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent
```

### MCP не работает в Cursor

```bash
# Убить старые процессы
pkill -f victoria_mcp_server
# Перезапустить Cursor
```

### Порты заняты

```bash
lsof -i :8010  # Victoria Agent
lsof -i :8011  # Veronica Agent
lsof -i :8012  # MCP Server
lsof -i :8080  # Backend
```

---

## 📚 Полная документация

- **`docs/VICTORIA_USAGE_GUIDE.md`** — полное руководство по всем режимам
- **`docs/VICTORIAATRA_HOW_TO_CALL.md`** — MCP инструменты в Cursor
- **`docs/VICTORIA_TERMINAL_CHAT_FLOW.md`** — как работает терминал
- **`docs/OPENWEBUI_RAG_SETUP.md`** — настройка Open WebUI
- **`VICTORIA.md`** — полная документация Victoria Agent

---

## 🎯 Когда что использовать

| Задача           | Режим                            |
| ---------------- | -------------------------------- |
| Работа с кодом   | **Cursor**                       |
| Вопросы / диалог | **Терминал чат** или **Cursor**  |
| Одна команда     | **Терминал команда**             |
| Браузер          | **Open WebUI**                   |
| Мобильный        | **Telegram**                     |
| Автоматизация    | **Терминал команда** или **API** |

---

**Справка по командам:**

```bash
# Cursor
@VictoriaATRA victoria_run goal="..."
@VictoriaATRA victoria_chat message="..."

# Терминал
bash scripts/chat_victoria.sh
python3 scripts/victoria_chat_standalone.py "..."

# API
curl http://localhost:8010/run -d '{"goal":"..."}'
curl http://localhost:8080/api/chat/ask-victoria -d '{"goal":"..."}'
```
