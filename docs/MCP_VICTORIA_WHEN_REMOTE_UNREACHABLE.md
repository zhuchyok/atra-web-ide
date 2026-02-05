# VictoriaATRA MCP: как сделать, если удалённый сервер недоступен

Если `http://185.177.216.15:8012/sse` не открывается (connection refused / timeout), Cursor не сможет подключиться к VictoriaATRA по этому URL. Ниже варианты, как сделать MCP работающим.

---

## Вариант 1: SSH-туннель (рекомендуется при доступе по SSH)

На **вашем Mac** в терминале:

```bash
# Проброс портов с сервера 185.177.216.15 на localhost
ssh -N -L 8012:localhost:8012 -L 8010:localhost:8010 zhuchyok@185.177.216.15
```

(замените `zhuchyok` на вашего пользователя на сервере; `-N` — только туннель, без shell).

Оставьте сессию открытой. Тогда:
- `localhost:8012` на Mac = порт 8012 на сервере (MCP)
- `localhost:8010` на Mac = порт 8010 на сервере (Victoria)

**В Cursor MCP настройте:**

```json
"VictoriaATRA": {
  "url": "http://localhost:8012/sse"
}
```

После этого VictoriaATRA будет работать через туннель.

---

## Вариант 2: MCP и Victoria только локально (без сервера)

Если хотите не зависеть от 185.177.216.15:

1. **Запустить Victoria (и при необходимости БД) локально:**

```bash
cd /Users/bikos/Documents/atra-web-ide
docker-compose -f knowledge_os/docker-compose.yml up -d
# Victoria будет на localhost:8010
```

2. **Запустить MCP-сервер локально:**

```bash
cd /Users/bikos/Documents/atra-web-ide
export VICTORIA_URL="http://localhost:8010"
python3 -m src.agents.bridge.victoria_mcp_server
# MCP будет на http://localhost:8012/sse
```

3. **В Cursor MCP:**

```json
"VictoriaATRA": {
  "url": "http://localhost:8012/sse"
}
```

Так VictoriaATRA работает полностью на вашей машине.

---

## Вариант 3: Починить доступ к 185.177.216.15

Чтобы работал прямой URL `http://185.177.216.15:8012/sse`, на сервере нужно:

1. **Запущены сервисы:**
   - Victoria (порт 8010)
   - Victoria MCP Server (порт 8012)

2. **Порты открыты:**
   - На сервере: `ss -tuln | grep -E ':(8010|8012)'`
   - В файрволе (iptables/ufw/облако): разрешён входящий трафик на 8010 и 8012

3. **Проверка с вашего Mac:**
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://185.177.216.15:8012/sse
   curl -s -o /dev/null -w "%{http_code}" http://185.177.216.15:8010/health
   ```
   Ожидается ответ 200 (или для SSE — успешное соединение).

---

## Итог

| Ситуация | Что сделать |
|----------|-------------|
| Есть SSH на 185.177.216.15 | Вариант 1: туннель + в Cursor `http://localhost:8012/sse` |
| Нет доступа к серверу / хотите всё локально | Вариант 2: Docker Victoria + локальный MCP + в Cursor `http://localhost:8012/sse` |
| Хотите ходить напрямую на 185.177.216.15 | Вариант 3: поднять сервисы и открыть порты на сервере |

Во всех рабочих случаях в Cursor в MCP указывается **один и тот же тип подключения** — SSE по URL (локальному или туннельному).
