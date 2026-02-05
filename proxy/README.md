# Прокси Claude Code → Victoria

Прокси принимает запросы в формате **Anthropic Messages API** (`POST /v1/messages`) и переводит их в вызов **Victoria** `POST /run`. Ответ Victoria возвращается в формате Anthropic. Так **Claude Code** (и другие клиенты Anthropic API) могут использовать **экспертов и оркестраторов** корпорации.

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `VICTORIA_URL` | `http://localhost:8010` | URL Victoria (POST /run). На 185: `http://localhost:8010` или `http://victoria-agent:8000` внутри Docker. |
| `VICTORIA_PROXY_TIMEOUT` | `600` | Таймаут запроса к Victoria (секунды). |
| `VICTORIA_RESPONSE_PREFIX` | `Виктория (корпорация): ` | Префикс, добавляемый к ответу (чтобы в Claude Code было видно, что отвечает Виктория). Пустая строка — без префикса. |
| `PORT` | — | Порт прокси (при запуске через uvicorn задаётся аргументом `--port`). |

## Запуск

**Важно:** команды нужно выполнять из **корня репозитория** (atra-web-ide), иначе Python не найдёт модуль `proxy`.

### Локально (рядом с Victoria на 8010)

```bash
cd /path/to/atra-web-ide
pip3 install -r proxy/requirements.txt
# или: python3 -m pip install -r proxy/requirements.txt
VICTORIA_URL=http://localhost:8010 uvicorn proxy.main:app --host 0.0.0.0 --port 8040
```

Прокси будет доступен на `http://localhost:8040`.

### На сервере 185

Если Victoria работает на 185 (например, через туннель или напрямую):

```bash
VICTORIA_URL=http://localhost:8010 uvicorn proxy.main:app --host 0.0.0.0 --port 8040
```

Снаружи: `http://185.177.216.15:8040` (если порт 8040 проброшен/открыт).

## Настройка Claude Code

Укажите Claude Code использовать прокси вместо облака Anthropic или Ollama. **Ключ должен быть непустым и в формате Anthropic** (клиент иначе пишет «Invalid API key»); прокси ключ не проверяет, подойдёт заглушка вида `sk-ant-api03-...`:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-placeholder-for-local-proxy"
export ANTHROPIC_BASE_URL=http://localhost:8040
# или для 185: export ANTHROPIC_BASE_URL=http://185.177.216.15:8040
```

Запускайте Claude Code из этого терминала (`claude launch`). Запросы пойдут в прокси → Victoria → эксперты и оркестраторы.

### Стриминг

Если клиент (Claude Code) отправляет запрос с **`stream: true`**, прокси возвращает ответ в формате **Anthropic Messages Streaming** (SSE): текст от Victoria разбивается по словам и отдаётся как события `content_block_delta`. В Claude Code ответ будет появляться по частям, как при стриминге от облака Anthropic. Victoria по-прежнему отвечает одним блоком; «стриминг» имитируется на стороне прокси.

**Один скрипт (прокси + Claude Code в OLL):** из корня репозитория `./scripts/launch_claude_with_victoria.sh` — поднимает прокси, запускает Claude Code с папкой OLL, по выходу останавливает прокси. Нужна Victoria на 8010.

## Проверка

- Прокси: `curl http://localhost:8040/health`
- Должен вернуть `victoria_reachable: true`, если Victoria доступна.

## 503 Service Unavailable

Если прокси возвращает **503** («Victoria disconnected or timed out»), значит Victoria (8010) закрыла соединение до ответа. Прокси делает до 3 попыток с паузами 2 и 4 с.

**Что проверить:**
1. Victoria запущена: `curl -s http://localhost:8010/health`
2. Логи Victoria в момент запроса — нет ли падений, таймаутов или OOM при тяжёлых запросах.
3. **Параллельные запросы:** Прокси **сериализует** вызовы Victoria (семафор 1): одновременно обрабатывается только один запрос к Victoria. Если Claude Code шлёт несколько запросов подряд, второй ждёт завершения первого — это устраняет типичные обрывы «Server disconnected» при 2+ параллельных запросах. Если 503 всё равно появляются — смотреть логи Victoria (падения, OOM, таймауты).
4. Таймаут: по умолчанию прокси ждёт ответ до 600 с (`VICTORIA_PROXY_TIMEOUT`). Увеличить при очень тяжёлых задачах.

## Как убедиться, что Claude Code ходит в Викторию (а не в Ollama/облако)

1. **Терминал прокси:** при каждом сообщении в Claude Code в логах uvicorn должна появляться строка вида `[PROXY] goal_preview=...`. Если её нет — запросы идут не на прокси (проверьте `ANTHROPIC_BASE_URL=http://localhost:8040` и перезапустите Claude Code из терминала, где задан этот env).
2. **Префикс в ответе:** прокси по умолчанию добавляет к ответу префикс **«Виктория (корпорация): »**, чтобы было видно, что отвечает Виктория, а не «сырая» модель (Qwen и т.д.). Отключить: `VICTORIA_RESPONSE_PREFIX=""`.

## См. также

- [docs/CLAUDE_CODE_LOCAL_MODELS.md](../docs/CLAUDE_CODE_LOCAL_MODELS.md) — подключение Claude Code к Ollama и к прокси.
- [docs/PROJECT_ARCHITECTURE_AND_GUIDE.md](../docs/PROJECT_ARCHITECTURE_AND_GUIDE.md) — порты и компоненты (Victoria 8010).
