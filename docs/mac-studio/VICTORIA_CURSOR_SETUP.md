# Подключение Victoria к Cursor при открытии проекта

## Быстрый старт

**При открытии нового проекта на Mac Studio:**

```bash
bash scripts/setup_victoria_cursor.sh
```

Скрипт автоматически:
1. Проверяет Victoria (localhost:8010)
2. Устанавливает `fastmcp` (если нужно)
3. Запускает MCP сервер Victoria (localhost:8012)
4. Выводит инструкцию для настройки MCP в Cursor

---

## Что происходит

### 1. Victoria Agent
- Работает в Docker контейнере `victoria-agent`
- HTTP API на **localhost:8010**
- Endpoints: `/run`, `/status`, `/health`

### 2. Victoria MCP Server
- Мост между Victoria и Cursor через MCP (Model Context Protocol)
- Запускается на **localhost:8012**
- SSE endpoint: `http://localhost:8012/sse`
- Tools: `victoria_run`, `victoria_status`, `victoria_health`

### 3. Cursor MCP
- Настройка в Cursor: **Settings → Features → MCP**
- Добавить сервер: `VictoriaATRA` (SSE, `http://localhost:8012/sse`)

---

## Использование в Cursor

После настройки MCP используй в чате:

```
@victoria_run 'проанализируй структуру проекта и предложи улучшения'
@victoria_status
@victoria_health
```

---

## Автоматический запуск при открытии проекта

### Вариант А: VS Code Tasks (рекомендуется)

Файл `.vscode/tasks.json` уже настроен — при открытии проекта в Cursor/VS Code автоматически запустится `setup_victoria_cursor.sh`.

### Вариант Б: Вручную

Добавь в `.cursorrules` или создай скрипт, который запускается при открытии:

```bash
# В корне проекта
bash scripts/setup_victoria_cursor.sh
```

---

## Проверка

```bash
# Victoria работает?
curl http://localhost:8010/health

# MCP сервер работает?
curl http://localhost:8012/sse

# Логи MCP
tail -f /tmp/victoria_mcp.log
```

---

## Устранение проблем

**Victoria не отвечает:**
```bash
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
```

**MCP сервер не запускается:**
```bash
pip3 install fastmcp
export PYTHONPATH=/path/to/atra:$PYTHONPATH
python3 -m src.agents.bridge.victoria_mcp_server
```

**Cursor не видит MCP:**
- Проверь, что MCP сервер запущен: `curl http://localhost:8012/sse`
- В Cursor: Settings → Features → MCP → проверь, что `VictoriaATRA` добавлен
- Перезапусти Cursor
