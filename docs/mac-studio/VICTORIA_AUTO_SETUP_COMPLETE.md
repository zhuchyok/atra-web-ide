# ✅ Автоматическая настройка Victoria для всех проектов Cursor — ЗАВЕРШЕНО

## 🎯 Что сделано

### 1. MCP сервер для Victoria

- **Файл:** `src/agents/bridge/victoria_mcp_server.py`
- **Порт:** 8012
- **SSE endpoint:** `http://localhost:8012/sse`
- **Tools:**
  - `victoria_run` — выполнить задачу через Victoria
  - `victoria_status` — проверить статус
  - `victoria_health` — health check

### 2. Автоматическая настройка MCP в Cursor

- **Скрипт:** `scripts/setup_cursor_mcp_global.py`
- **Результат:** VictoriaATRA добавлен в `~/Library/Application Support/Cursor/User/settings.json`
- **Статус:** ✅ Выполнено

### 3. Автоматическое подключение при открытии проекта

- **Скрипт:** `scripts/victoria_auto_connect.sh`
- **Автозапуск:** `.vscode/tasks.json` (запускается при открытии проекта)
- **Функция:** Автоматически проверяет и запускает Victoria + MCP сервер

### 4. Глобальная настройка (один раз)

- **Скрипт:** `scripts/final_victoria_setup.sh`
- **Что делает:**
  1. Настраивает MCP в Cursor settings
  2. Проверяет Victoria
  3. Устанавливает fastmcp
  4. Запускает MCP сервер

---

## 🚀 Как использовать

### Первоначальная настройка (один раз):

```bash
cd /Users/zhuchyok/Documents/GITHUB/atra/atra
bash scripts/final_victoria_setup.sh
```

### Перезапуск Cursor:

После настройки **перезапусти Cursor**, чтобы применить MCP настройки.

### Использование в любом проекте:

После перезапуска Cursor в **любом проекте** используй:

```
@victoria_run 'проанализируй код и предложи улучшения'
@victoria_status
@victoria_health
```

---

## 🔄 Автоматическая работа

### При открытии проекта:

1. `.vscode/tasks.json` автоматически запускает `victoria_auto_connect.sh`
2. Скрипт проверяет Victoria (localhost:8010)
3. Скрипт проверяет MCP сервер (localhost:8012)
4. Если не запущены — запускает автоматически

### Требования:

- Docker запущен
- Victoria контейнер работает (или будет запущен автоматически)
- fastmcp установлен (установится автоматически при первом запуске)

---

## 📋 Проверка статуса

```bash
# Victoria работает?
curl http://localhost:8010/health

# MCP сервер работает?
curl http://localhost:8012/sse

# Логи MCP
tail -f /tmp/victoria_mcp.log
```

---

## 🛠️ Ручной запуск (если нужно)

```bash
# Запуск Victoria через Docker
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent

# Запуск MCP сервера
cd /Users/zhuchyok/Documents/GITHUB/atra/atra
export PYTHONPATH="$PWD:$PYTHONPATH"
python3 -m src.agents.bridge.victoria_mcp_server
```

---

## ✅ Итог

**Всё настроено автоматически:**

- ✅ MCP добавлен в Cursor settings (глобально)
- ✅ Автоматическое подключение при открытии проекта
- ✅ MCP сервер готов к работе
- ✅ Victoria доступна через `@victoria_run` в любом проекте

**Осталось только:**

1. Перезапустить Cursor
2. Использовать `@victoria_run` в чате

---

_Создано: 2026-01-23_
