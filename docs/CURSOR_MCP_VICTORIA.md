# Подключение Victoria к чату Cursor через MCP

Когда Victoria MCP настроен, **запросы из чата Cursor идут напрямую к Виктории**: Cursor видит инструменты `victoria_run`, `victoria_status`, `victoria_health` и может вызывать их по вашей просьбе.

## Что нужно

1. **Victoria Agent** — работает на порту 8010 (Docker: `victoria-agent`).
2. **Victoria MCP Server** — работает на порту 8012, отдаёт SSE для Cursor.
3. **Cursor** — в настройках добавлен MCP‑сервер VictoriaATRA.

## Шаг 1: Запустить Victoria MCP Server

Нужен Python с установленным `fastmcp` (в проекте — venv backend). Из корня проекта:

```bash
./scripts/start_victoria_mcp.sh
```

Или напрямую:

```bash
cd /Users/bikos/Documents/atra-web-ide
backend/.venv/bin/python3 -m src.agents.bridge.victoria_mcp_server
```

Сервер слушает `http://localhost:8012`, путь для Cursor: `http://localhost:8012/sse`.

Чтобы запустить в фоне (логи в файл):

```bash
nohup ./scripts/start_victoria_mcp.sh >> /tmp/victoria_mcp.log 2>&1 &
```

Если `ModuleNotFoundError: No module named 'mcp'` — установите зависимости: `pip install fastmcp` (или в backend venv: `backend/.venv/bin/pip install fastmcp`).

Проверка:

```bash
curl -s http://localhost:8012/sse
# Должен открыться SSE‑поток (или ответ от MCP).
```

## Шаг 2: Добавить MCP в Cursor

Один раз:

```bash
python3 scripts/victoria/setup_cursor_mcp_global.py
```

Скрипт прописывает в Cursor (глобальные настройки):

- **VictoriaATRA** → `http://localhost:8012/sse` (тип: sse).

После этого **перезапусти Cursor**, чтобы подхватить MCP.

## Шаг 3: Использование в чате Cursor

В чате Cursor можно писать, например:

- «Спроси Викторию: привет»
- «Вызови victoria_chat с сообщением: расскажи о проекте»
- «Вызови victoria_run с задачей: покажи статус проекта»
- «Проверь victoria_health»

**Инструменты MCP:**
- `victoria_chat` — диалог с Викторией (сообщение + опционально история)
- `victoria_run` — выполнить задачу (goal + max_steps)
- `victoria_status` — статус Victoria Agent
- `victoria_health` — health check

Cursor будет вызывать нужный инструмент и показывать ответ Виктории.

## Если Victoria на другой машине (Mac Studio)

Запусти MCP с переменной:

```bash
VICTORIA_URL=http://192.168.1.64:8010 python3 -m src.agents.bridge.victoria_mcp_server
```

Или пропиши `VICTORIA_URL` в `.env` и при запуске MCP он подхватит значение (если скрипт читает `.env`).

## Порты

| Сервис              | Порт | Назначение                    |
|---------------------|------|-------------------------------|
| Victoria Agent      | 8010 | API Виктории (`/run`, `/health`) |
| Victoria MCP Server | 8012 | MCP для Cursor (SSE: `/sse`)  |

## Автозапуск MCP (опционально)

На macOS можно поднять MCP через launchd (см. `scripts/setup_complete_autostart.sh` или `docs/mac-studio/AUTOSTART_COMPLETE.md`). Тогда после перезагрузки Victoria MCP будет стартовать сам.
