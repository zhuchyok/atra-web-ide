# Runbook: Open WebUI → ask_victoria → Victoria (Singularity 15.0)

Пошаговая настройка сценария: запрос из Open WebUI → инструмент ask_victoria → ответ Victoria.

## 0. Запуск одной командой (рекомендуется)

Из корня репозитория:

```bash
./scripts/start_singularity_15_openwebui.sh
```

Поднимет сеть, db, redis, Victoria и Open WebUI. С бэкендом (метрики, прокси):

```bash
./scripts/start_singularity_15_openwebui.sh --with-backend
```

Проверка готовности:

```bash
./scripts/verify_singularity_15_openwebui.sh
```

Дальше — разделы 2–3 (настройка Open WebUI и тест).

## 1. Поднять среду (вручную)

### 1.1 Сеть (один раз)

```bash
docker network create atra-network 2>/dev/null || true
```

### 1.2 Victoria и Open WebUI (Knowledge OS)

```bash
cd /path/to/atra-web-ide
docker compose -f knowledge_os/docker-compose.yml up -d db redis victoria-agent open-webui
```

Проверка Victoria:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8010/health
# ожидается 200 (порт 8010 — с хоста; внутри сети victoria-agent:8000)
```

### 1.3 Бэкенд atra-web-ide (опционально)

Если нужны метрики и лимиты через бэкенд:

```bash
docker compose up -d backend
```

Проверка бэкенда:

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health
# ожидается 200
```

## 2. Настройка Open WebUI

- Откройте Open WebUI: **http://localhost:3005** (порт из knowledge_os/docker-compose: 3005→8080).

### 2.0 Всё из одного файла (рекомендуется)

После запуска стека выполните один раз:
```bash
python3 scripts/openwebui_bootstrap_singularity_15.py
```
Откройте файл **configs/openwebui_singularity_15_oneload/SYSTEM_PROMPT_AND_TOOL.txt**: в нём готовый системный промпт и инструкция по добавлению инструмента. Скопируйте системный промпт в Open WebUI → модель Victoria → System Prompt; затем Workspace → Tools → Import Tools → выберите `configs/openwebui_ask_victoria_tool.py`.

### 2.1 Системный промпт (Golden Persona)

Системный промпт должен быть задан **в пресете**, которым вы пользуетесь (иначе модель отвечает от своего имени — например, Qwen скажет «Я Qwen»).

1. В Open WebUI: **Пресеты** → выберите пресет (например **victoria.singularity.15**) → откройте его **редактирование** (иконка карандаша / Edit).
2. Найдите поле **System Prompt** (или **Системное сообщение** / **Default system message** / **Prompt**) и вставьте туда полный текст из **configs/openwebui_singularity_15_oneload/SYSTEM_PROMPT_AND_TOOL.txt** (только блок до строки «=== ИНСТРУМЕНТ ===»).
3. Сохраните пресет.
4. **Важно:** откройте **новый чат** (старый мог создаться без системного промпта). В новом чате выберите этот пресет и модель (например qwen1.5-coder-32b), включите инструмент ask_victoria и спросите «кто ты?» — ответ должен быть от имени Виктории.

Если модель всё равно представляется как Qwen/другая — промпт не подхватился: проверьте, что правите именно пресет, а не глобальные настройки модели, и что в пресете выбран тот же системный промпт (в некоторых версиях есть отдельный выбор «System prompt» из списка или вкладка «Prompt»).

### 2.2 Инструмент ask_victoria

**Вариант A — Python-инструмент (рекомендуется)**

1. Workspace → **Tools** → **Import Tools**.
2. Укажите файл **configs/openwebui_ask_victoria_tool.py** из клона репозитория (на хосте при импорте выберите этот файл). В контейнере Open WebUI файл смонтирован как **/workspace/configs/openwebui_ask_victoria_tool.py** — если интерфейс позволяет указать путь внутри контейнера, можно использовать его.
3. В настройках инструмента (Valves). **Рекомендуется — как Cursor/backend** (один канал, 3 ретрая, таймаут 900 с):
   - **USE_BACKEND_PROXY:** `true`
   - **VICTORIA_URL:** `http://atra-web-ide-backend:8000` (внутри Docker-сети контейнер слушает порт 8000; 8080 — только на хосте).
   Тогда запросы идут через `POST /api/chat/ask-victoria` и тот же VictoriaClient, что и чат Cursor — меньше RemoteProtocolError и обрывов.
   Альтернатива (напрямую к Victoria): **USE_BACKEND_PROXY:** `false`, **VICTORIA_URL:** `http://victoria-agent:8000`.
   - **ASK_VICTORIA_TIMEOUT:** при необходимости увеличьте (по умолчанию 600; при прокси через бэкенд бэкенд использует свой VICTORIA_TIMEOUT, например 900).

**Вариант B — через конфиг API (если Open WebUI поддерживает)**

Используйте **configs/openwebui_ask_victoria_tool.json**: URL задать `http://atra-web-ide-backend:8080/api/chat/ask-victoria` при работе через бэкенд или настроить вызов Victoria по документации Open WebUI.

## 3. Проверка сценария

1. В Open WebUI выберите модель, у которой задан системный промпт из SINGULARITY_15_GOLDEN_PERSONA.md и подключён инструмент ask_victoria.
2. Отправьте запрос, например: **«Проверь бэкенд»** или **«Кратко ответь: какой у тебя статус?»**.
3. Ожидание: модель вызывает инструмент ask_victoria → запрос уходит в Victoria → в чат возвращается ответ Victoria (а не симуляция эксперта).

Если используется бэкенд:

```bash
curl -s http://localhost:8080/metrics/summary | grep -E "ask_victoria|status"
# после запроса должен появиться/увеличиться счётчик ask_victoria_total
```

## 4. Типичные проблемы

| Симптом | Что проверить |
|--------|----------------|
| Модель отвечает «Я Qwen» / «Я Claude» вместо Виктории | Системный промпт задан **в пресете** (Пресеты → Edit пресета → System Prompt)? Откройте **новый чат** после сохранения пресета. |
| «Victoria is temporarily unavailable» / **RemoteProtocolError** | Переведи Open WebUI **на прокси через бэкенд** (как Cursor): Valves → USE_BACKEND_PROXY=true, VICTORIA_URL=http://atra-web-ide-backend:8000. Бэкенд использует VictoriaClient с **3 ретраями** и таймаутом 900 с — меньше обрывов. Если оставляешь прямой вызов Victoria — увеличь ASK_VICTORIA_TIMEOUT, упрости запрос или повтори через минуту. Проверка: `docker exec open-webui curl -s http://victoria-agent:8000/health` или `curl -s http://localhost:8080/health`. |
| Инструмент не вызывается | Системный промпт скопирован полностью? Модель поддерживает function calling? В чате включён инструмент ask_victoria? |
| 503 от бэкенда | Лимит слотов Victoria (MAX_CONCURRENT_VICTORIA) — сообщение «Too many requests». Или ошибка Victoria — в теле ответа теперь краткая причина: таймаут / нет связи / перегрузка. Запустите диагностику: `./scripts/test_ask_victoria_chain.sh`. |
| Таймаут | Увеличить ASK_VICTORIA_TIMEOUT в Valves (рекомендуется 300–600 для анализа/оркестрации). Если запрос всё равно обрывается — см. ниже «Таймауты Open WebUI». |

### Диагностика цепочки Backend → Victoria

С хоста (backend на 8080):

```bash
./scripts/test_ask_victoria_chain.sh
```

Скрипт проверяет `/health` и один вызов `POST /api/chat/ask-victoria` с простой целью. При 503 в ответе выводится понятное сообщение (таймаут / нет связи с Victoria / перегрузка). Переменные: `BACKEND_URL` (default `http://localhost:8080`), `ASK_TIMEOUT` (default 120 с).

**Если Victoria перезапускается:** в первые 1–2 минуты после старта контейнера Victoria прогревает модели и может не принимать запросы или обрывать соединение. Бэкенд делает 3 ретрая с задержками 5 и 10 с — при повторной попытке через минуту запрос часто проходит. При частых перезапусках проверьте логи Victoria (`docker logs victoria-agent`) и память (OOM). **Обход:** если из контейнера бэкенда до victoria-agent:8000 стабильно «connection refused», задайте в backend env `VICTORIA_URL=http://host.docker.internal:8010` — запросы пойдут через хост (порт 8010).

### Таймауты Open WebUI (если длинные задачи обрываются)

Open WebUI ограничивает время ожидания на стороне бэкенда. Переменные окружения контейнера (или хоста, если запуск не в Docker):

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| **AIOHTTP_CLIENT_TIMEOUT** | 300 (сек) | Общий таймаут клиента (Ollama, OpenAI, возможно весь запрос чата с инструментами). Увеличь до 600–900 или пустая строка `""` — без лимита. |
| **AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA** | 10 (сек) | Таймаут получения данных от tool server. Если вызовы инструментов режутся через ~10 с — увеличь до 600 и больше. |

Где задать: при запуске в Docker — в `docker-compose` или `.env` для сервиса `open-webui`, например:

```yaml
environment:
  AIOHTTP_CLIENT_TIMEOUT: "600"
  AIOHTTP_CLIENT_TIMEOUT_TOOL_SERVER_DATA: "600"
```

После изменения — перезапуск контейнера Open WebUI. См. [Open WebUI Env Configuration](https://docs.openwebui.com/reference/env-configuration).

## 5. Краткий чеклист

- [ ] Сеть `atra-network` создана
- [ ] Запущены `victoria-agent` и `open-webui` (при необходимости — `backend`)
- [ ] В Open WebUI задан системный промпт из **docs/SINGULARITY_15_GOLDEN_PERSONA.md**
- [ ] Добавлен инструмент ask_victoria (файл **configs/openwebui_ask_victoria_tool.py** или JSON)
- [ ] Valves: VICTORIA_URL и USE_BACKEND_PROXY соответствуют запущенным сервисам
- [ ] Тестовый запрос в чате → вызов ask_victoria → ответ Victoria в чате

## 6. Установка Open WebUI с нуля (опционально)

Если нужен чистый сброс и автоматическое создание админа:
```bash
./scripts/openwebui_fresh_install_singularity_15.sh
```
Задайте в .env или export: `OPENWEBUI_ADMIN_EMAIL`, `OPENWEBUI_ADMIN_PASSWORD`. После установки войдите в Open WebUI и выполните шаги из §2.0 (один файл).

## 7. Автозапуск (чтобы всё поднималось автоматически)

- **При каждом входе в систему:** выполните один раз `./scripts/setup_singularity_15_autostart.sh` — при следующем входе launchd поднимет контейнеры (Victoria, Open WebUI).
- **Полная настройка:** `./scripts/setup_complete_autostart.sh` — Docker, Ollama, контейнеры (в т.ч. Open WebUI :3005) поднимаются при старте.
- **Проверка контейнеров:** `./scripts/check_and_start_containers.sh` — при необходимости поднимет и Open WebUI.

## 8. Автоматизация «сделай всё сама»

- Запуск стека: `./scripts/start_singularity_15_openwebui.sh [--with-backend]`
- Генерация файла с системным промптом и инструкцией: `python3 scripts/openwebui_bootstrap_singularity_15.py` → файл **configs/openwebui_singularity_15_oneload/SYSTEM_PROMPT_AND_TOOL.txt**
- Один раз вручную: открыть этот файл, скопировать системный промпт в Open WebUI, добавить инструмент из `configs/openwebui_ask_victoria_tool.py`. Дальше сценарий Open WebUI → ask_victoria → Victoria работает без дополнительных шагов.

---

*См. также: docs/OPENWEBUI_RAG_SETUP.md, docs/SINGULARITY_15_GOLDEN_PERSONA.md*
