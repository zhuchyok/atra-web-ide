# Полное руководство: Как использовать Викторию

Виктория (Team Lead Atra Core) доступна в **4 режимах**: Cursor, терминал чат, терминал команды и Open WebUI. Выбирайте режим под свою задачу.

---

## 🎯 Какой режим для какой задачи

| Задача               | Рекомендуемый режим             | Почему                                                                    |
| -------------------- | ------------------------------- | ------------------------------------------------------------------------- |
| Работа с кодом в IDE | **Cursor MCP**                  | Контекст открытых файлов, git status, автоматическое применение изменений |
| Диалог / вопросы     | **Терминал чат** или **Cursor** | Быстрый интерактивный диалог, история сохраняется                         |
| Разовая команда      | **Терминал команда**            | Одна задача → один ответ, удобно для скриптов и автоматизации             |
| Браузерный интерфейс | **Open WebUI**                  | Красивый UI, доступ из браузера, RAG по документам                        |
| Telegram             | **Telegram бот**                | Мобильный доступ, уведомления, групповые чаты                             |

---

## 1️⃣ Cursor (MCP интеграция) — работа в IDE

### Что запустить

```bash
# 1. Victoria Agent (если ещё не запущен)
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent

# 2. Victoria MCP Server запускается автоматически Cursor'ом
# Проверка: в Cursor должен быть зелёный индикатор MCP сервера VictoriaATRA
```

### Как использовать в чате Cursor

Просто **пишите запрос своими словами**, Cursor автоматически выберет нужный инструмент:

```
Примеры:
• "Вызови Викторию с задачей: проанализируй структуру backend и предложи улучшения"
• "Спроси Викторию: какие эксперты есть в корпорации?"
• "Проверь victoria_health"
```

### Доступные инструменты MCP

| Инструмент                  | Назначение                             | Параметры                                                    |
| --------------------------- | -------------------------------------- | ------------------------------------------------------------ |
| `victoria_run`              | Запуск задачи (оркестратор → эксперты) | `goal` (обязательно), `max_steps` (по умолчанию 500)         |
| `victoria_chat`             | Диалог с Викторией                     | `message` (обязательно), `history_json`, `project_context`   |
| `victoria_health`           | Проверка доступности                   | -                                                            |
| `victoria_status`           | Статус агента и база знаний            | -                                                            |
| `victoria_execute_plan`     | Получить план и выполнить              | `goal`, `workspace_path`, `max_steps`                        |
| `victoria_run_with_context` | Запуск с полным IDE контекстом         | `goal`, `open_files_json`, `git_status`, `cursor_rules_json` |
| `victoria_batch_read`       | Пакетное чтение файлов                 | `file_paths_json`, `workspace_path`                          |
| `victoria_batch_grep`       | Пакетный поиск по паттерну             | `pattern`, `file_paths_json`, `workspace_path`               |

### Примеры команд в Cursor

```
# Запуск задачи
"Вызови victoria_run с goal: добавь в README раздел про запуск"

# Диалог
"Вызови victoria_chat с сообщением: кто такой Артём и чем он занимается?"

# Проверка здоровья
"Вызови victoria_health"

# Пакетное чтение
"Вызови victoria_batch_read для файлов: src/main.py, src/utils.py, README.md"
```

### Явный вызов через @mention

```
@VictoriaATRA victoria_run goal="Проверь, что в backend есть эндпоинт /health"
```

### Что должно быть настроено

Файл `.cursor/settings.json` уже содержит конфигурацию:

```json
{
  "mcpServers": {
    "VictoriaATRA": {
      "command": "bash",
      "args": [
        "/Users/bikos/Documents/atra-web-ide/scripts/start_victoria_mcp.sh"
      ],
      "cwd": "/Users/bikos/Documents/atra-web-ide",
      "env": {
        "VICTORIA_URL": "http://localhost:8010"
      }
    }
  }
}
```

Скрипт `start_victoria_mcp.sh` автоматически:

- Создаёт виртуальное окружение `.venv-agents` (если нет)
- Устанавливает зависимости `fastmcp`, `httpx` (если нет)
- Запускает MCP сервер на порту 8012

---

## 2️⃣ Терминал: интерактивный чат

### Запуск

```bash
# Локальная Victoria (порт 8010)
bash scripts/chat_victoria.sh

# Удалённая Victoria (Mac Studio)
VICTORIA_REMOTE_URL=http://your-mac-studio-ip:8010 bash scripts/chat_victoria.sh
```

### Как работает

- **Интерактивный режим:** вводите сообщения, получаете ответы
- **История сохраняется** в течение сессии
- **Контекст проекта** можно задать через `PROJECT_CONTEXT=setki-21`
- **Session ID** автоматически генерируется (для LTM)

### Примеры диалога

```
╔════════════════════════════════════════════════╗
║           💬 ЧАТ С ВИКТОРИЕЙ                  ║
║      Team Lead корпорации Singularity 21.5    ║
╚════════════════════════════════════════════════╝

Victoria > Привет, Виктория! Как дела?

✨ Victoria:
Привет! Я на связи. Работаю в полном режиме:
• 86 экспертов готовы к работе
• База знаний проиндексирована (45К+ узлов)
• Enhanced режим включён
Чем могу помочь?

Victoria > Кто такой Игорь?

✨ Victoria:
Игорь — наш Backend Developer, эксперт по восстановлению систем.
Тот самый специалист, который восстанавливал 46-й сервер после падения.
Мастер Docker и реанимации инфраструктуры.
```

### Горячие клавиши

- `Ctrl+C` — выход из чата
- `Ctrl+D` — завершение ввода (если многострочный режим)
- `/clear` — очистить историю текущей сессии
- `/help` — справка

### Переменные окружения

```bash
# URL Victoria Agent
VICTORIA_URL=http://localhost:8010

# Или удалённый
VICTORIA_REMOTE_URL=http://192.168.1.100:8010

# Контекст проекта
PROJECT_CONTEXT=atra-web-ide  # по умолчанию

# Таймаут запроса (секунды)
VICTORIA_TIMEOUT=600  # по умолчанию 10 минут
```

### Через какую модель обрабатывается

| Тип запроса         | Путь обработки         | Модель                                               |
| ------------------- | ---------------------- | ---------------------------------------------------- |
| Простые приветствия | Fast Path              | MLX или Ollama: `victoria-wisdom-v3.5` / `tinyllama` |
| Вопросы / диалог    | Fast Path              | MLX или Ollama: `victoria-wisdom-v3.5`               |
| Сложные задачи      | Victoria Enhanced      | Ollama/MLX через ai_core: `victoria-wisdom-v3.5`     |
| Работа с кодом      | Victoria Agent (ReAct) | Ollama: planner + executor (`VICTORIA_MODEL`)        |

Подробно: `docs/VICTORIA_TERMINAL_CHAT_FLOW.md`

### Проверка цепочки: мозг (MLX), руки (Ollama), эксперты, v3.5 (2026-03-06)

- **Тестовый запрос:** `POST http://localhost:8010/run?async_mode=true` с `goal`, `project_context` → 202 + `task_id`; опрос `GET /run/status/{task_id}`. Синхронный вариант: `async_mode=false` (таймаут до 90+ с).
- **По логам контейнера** (`docker logs victoria-agent --tail 300`):
  - **MLX:** проверяется по `GET http://host.docker.internal:11435/health` (200 OK). Используется в путях, где вызывается `local_router.run_local_llm` (ai_core, часть Enhanced).
  - **Ollama (руки):** стратегия, `understand_goal` и шаги ReAct идут через **OllamaExecutor** в `victoria_server` → `http://host.docker.internal:11434/api/chat` и `/api/generate` с моделью **victoria-wisdom-v3.5:latest**. Эмбеддинги — `POST .../api/embeddings`.
  - **Эксперты и оркестрация:** в логах видны `USE_VICTORIA_ENHANCED: True`, Victoria Enhanced (категория, метод=react), ReAct цикл с принудительной моделью `victoria-wisdom-v3.5:latest` (GOD MODE). Участие экспертов и оркестратора подтверждается цепочкой: strategy → understand_goal → Enhanced → ReAct.
- **Конфигурация victoria-agent (docker-compose):** `VICTORIA_MODEL` и `VICTORIA_PLANNER_MODEL`: `victoria-wisdom-v3.5:latest`; `VICTORIA_USE_LOCAL_ROUTER: "true"`; `VICTORIA_FORCE_STEP_MODEL: "victoria-wisdom-v3.5:latest"`; `OLLAMA_BASE_URL`/`MLX_API_URL` на host.docker.internal:11434/11435.
- **local_router.py (v3.5):** `OLLAMA_MODELS_FALLBACK` и `MLX_MODELS_FALLBACK` для категорий reasoning/coding/default/chat — везде `victoria-wisdom-v3.5` / `victoria-wisdom-v3.5:latest`. В `available_models_scanner.py`: `OLLAMA_BEST_FIRST` и `MLX_BEST_FIRST` начинаются с v3.5. Поддержка v3.5 в цепочке подтверждена.

**Итог:** Запрос к локальной Виктории проходит; в текущем пути `/run` стратегия и исполнение идут через Ollama (v3.5). MLX участвует при вызовах через local_router (например из ai_core). Эксперты и оркестрация (Enhanced, ReAct, v3.5 MoE) задействованы; конфигурация victoria-agent и local_router поддерживает v3.5.

---

## 3️⃣ Терминал: одноразовые команды

### Запуск

```bash
# Прямой вызов
python3 scripts/victoria_chat_standalone.py "Проверь статус backend"

# Через переменные окружения
VICTORIA_URL=http://localhost:8010 \
PROJECT_CONTEXT=atra-web-ide \
python3 scripts/victoria_chat_standalone.py "Покажи список файлов в backend/"
```

### Примеры команд

```bash
# Простой вопрос
python3 scripts/victoria_chat_standalone.py "Какие эксперты есть в корпорации?"

# Задача на выполнение
python3 scripts/victoria_chat_standalone.py "Проверь, что все тесты проходят"

# С контекстом другого проекта
PROJECT_CONTEXT=setki-21 python3 scripts/victoria_chat_standalone.py "Статус базы данных"

# Удалённая Victoria
VICTORIA_REMOTE_URL=http://192.168.1.100:8010 \
python3 scripts/victoria_chat_standalone.py "Привет!"
```

### Использование в скриптах

```bash
#!/bin/bash
# Пример: автоматическая проверка backend

RESPONSE=$(python3 scripts/victoria_chat_standalone.py "Проверь backend health endpoint")

if echo "$RESPONSE" | grep -q "ok"; then
    echo "✅ Backend работает"
else
    echo "❌ Backend не отвечает"
    exit 1
fi
```

### Формат ответа

Команда выводит **только ответ Виктории** (без промптов и форматирования), удобно для автоматизации:

```bash
$ python3 scripts/victoria_chat_standalone.py "Статус агентов"
Victoria Agent: ✅ онлайн (порт 8010)
Veronica Agent: ✅ онлайн (порт 8011)
База знаний: 45K+ узлов
86 экспертов готовы к работе
```

---

## 4️⃣ Open WebUI — браузерный интерфейс

### Что запустить

```bash
# 1. Victoria Agent (если ещё не запущен)
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent

# 2. Backend (если используете прокси)
docker-compose up -d backend

# 3. Open WebUI (если ещё не запущен)
docker-compose up -d openwebui
```

### Настройка в Open WebUI

#### Шаг 1: Добавить инструмент ask_victoria

1. Откройте Open WebUI → **Workspace** → **Tools**
2. Нажмите **Import Tools**
3. Выберите файл: `configs/openwebui_ask_victoria_tool.py`
4. Настройте Valves:
   - `VICTORIA_URL`: `http://victoria-agent:8000` (в Docker) или `http://localhost:8010` (с хоста)
   - `USE_BACKEND_PROXY`: `false` (прямой вызов) или `true` (через backend)
   - `ASK_VICTORIA_TIMEOUT`: `600` (10 минут)

#### Шаг 2: Загрузить документы для RAG (опционально)

Open WebUI → **Workspace** → **Documents** → загрузите:

- `docs/MASTER_REFERENCE.md` — библия проекта
- `docs/COGNITIVE_CODE.md` — когнитивный кодекс
- `.cursorrules` — правила проекта

Привяжите к коллекции "Victoria" для автоматического RAG.

#### Шаг 3: Настроить системный промпт

Для моделей, которые должны делегировать в Victoria, задайте промпт из:
`docs/SINGULARITY_15_GOLDEN_PERSONA.md`

Это заставит внешнюю модель **всегда** использовать инструмент `ask_victoria` вместо симуляции экспертов.

### Использование в Open WebUI

После настройки просто пишите запросы в чат:

```
Пользователь:
Привет, Виктория! Проверь статус backend и расскажи о последних изменениях.

Модель с Golden Persona:
[Вызывает ask_victoria с goal="Проверь статус backend и расскажи о последних изменениях"]

Victoria (через инструмент):
✅ Backend работает на порту 8080
Последние изменения:
• Добавлен семафор MAX_CONCURRENT_VICTORIA=50
• Исправлена маршрутизация при перегрузке (503 + Retry-After)
• Обновлены метрики Prometheus
Подробности в docs/CHANGES_FROM_OTHER_CHATS.md
```

### Прямой вызов через API

```bash
# Через backend прокси
curl -X POST http://localhost:8080/api/chat/ask-victoria \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Проверь статус backend",
    "project_context": "atra-web-ide",
    "user_key": "openwebui-user123"
  }'

# Прямо в Victoria
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Проверь статус backend",
    "project_context": "atra-web-ide",
    "max_steps": 20
  }'
```

### Как отследить, делает ли Виктория задачу

| Способ                                    | Когда использовать                                                                                                                                                                                                        |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Синхронный POST /run** (без async_mode) | Ответ в теле запроса; ждёте до таймаута — видно только по завершению.                                                                                                                                                     |
| **Асинхронный 202 + опрос**               | Задача в фоне: `POST /run?async_mode=true` → в ответе `task_id` и `status_url`. Опрашивайте `GET http://localhost:8010/run/status/{task_id}` — поля `status` (queued → processing → completed/failed), `stage`, `output`. |
| **Логи контейнера**                       | В реальном времени: `docker logs -f victoria-agent`. Ищите `[VICTORIA_CYCLE]`, `[TRACE] _run_task_background`, `[AGENT_RUN]`, `route=enhanced` / `route=agent_run` — видно этап и кто выполняет.                          |
| **VICTORIA_DEBUG=true**                   | В .env или перед запуском: больше DEBUG-логов по маршрутизации и шагам.                                                                                                                                                   |

### Асинхронный режим: два шага (для долгих задач и аудитов)

Чтобы не держать терминал открытым, пока Виктория выполняет долгую задачу (аудит, анализ), используйте асинхронный режим.

**Шаг 1: Отправка задачи (получение `task_id`)**

Добавьте `?async_mode=true` в URL. Ответ вернётся сразу, в теле будет `task_id`.

```bash
curl -X POST "http://localhost:8010/run?async_mode=true" \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Виктория, привет! Проведи полный аудит сайта в /Users/bikos/Documents/dev/setki-21 (ветка studio). Проверь SEO, технические ошибки, UI/UX и адрес в Чебоксарах (ул. Гражданская, 53). Ждем отчет.",
    "project_context": "setki-21",
    "use_enhanced": true
  }'
```

Пример ответа: `{"status": "accepted", "task_id": "550e8400-e29b-41d4-a716-446655440000"}`

**Шаг 2: Проверка статуса и получение отчёта**

Подставьте полученный `task_id` в запрос — опрашивайте, пока `status` не станет `completed` или `failed`; в `output` будет итог.

```bash
# Замените ID на тот, который получили в шаге 1
curl -s "http://localhost:8010/run/status/550e8400-e29b-41d4-a716-446655440000"
```

В ответе: `status` (queued → processing → completed/failed), `stage`, `output` (когда completed).

**Зачем так делать для аудита**

1. **Таймауты:** Полный аудит может занять 2–5 минут. Обычный `curl` без async может оборваться по таймауту; в асинхронном режиме Виктория доделает работу в фоне.
2. **Контроль:** В любой момент можно проверить статус и не блокировать терминал.
3. **Логи:** Пока задача в фоне, можно смотреть логи: `docker logs -f victoria-agent`.

Если нужен ответ «здесь и сейчас» в том же запросе — используйте `POST /run` без `?async_mode=true` (синхронный режим).

### Куратор: как ставить задачи и проконтролировать (стриминг, скрипт, API)

**Правило (все должны знать):** Когда Cursor-агент или человек выступает в роли **куратора** (даёт задание Виктории и контролирует результат), **рекомендуется всегда** давать задание через **скрипт куратора** `scripts/curator_send_tasks_to_victoria.py` (с `--file` для цели и `--async --max-wait 600`). Скрипт сам опрашивает статус и при `completed` пишет отчёт в `docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json` и `.md`. «Виктория сделала» = появление этого файла; куратор открывает отчёт и при необходимости применяет правки из `output`. Не использовать голый `POST /run?async_mode=true` без скрипта — иначе отчёт не сохранится и отслеживание вручную.

Когда ты в роли **куратора**, удобны три способа:

| Способ                                | Что даёт                                                                                                                                 | Когда использовать                                                                                           |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Скрипт куратора** (рекомендуется)   | Задача из **файла** → автоопрос статуса → **отчёт в файл** (JSON + MD в `docs/curator_reports/`). «Готово» = появление файла.            | **Всегда**, когда куратор даёт задание Виктории (длинные задачи, отчёт в репо, не нужно вручную опрашивать). |
| **POST /stream** (SSE)                | Ответ **потоком в реальном времени**: шаги (thought, step), скилл, IDE context, затем текст ответа. Одно соединение, без опроса статуса. | Хочешь видеть, как Виктория думает и что делает по шагам.                                                    |
| **POST /run?async_mode=true** + опрос | 202 + task_id, дальше сам опрашиваешь GET /run/status. Отчёт в curator_reports **не** создаётся.                                         | Только если скрипт куратора недоступен (минимальный вариант из кода).                                        |

**Как «уведомление» о завершении:** Виктория сама никуда не шлёт push (нет webhook/callback при completed). Отслеживание = **скрипт куратора** опрашивает `GET /run/status/{task_id}` каждые 2.5 с; при `status=completed` пишет отчёт в `docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json` (полный `output`) и `.md` (превью). То есть «Виктория сделала» = появление/обновление этого файла; Cursor-агент может прочитать отчёт и продолжить (например, применить правки из output). Подробнее: `scripts/curator_send_tasks_to_victoria.py`, `docs/CURATOR_RUNBOOK.md`.

**1. Стриминг (видеть шаги в реальном времени):**

```bash
curl -N -X POST http://localhost:8010/stream \
  -H "Content-Type: application/json" \
  -d '{"goal": "Проанализируй .cursor/rules/victoria.mdc на устаревшее", "project_context": "atra-web-ide", "max_steps": 80}'
```

В ответе — поток SSE: события `type: step` (thought, title, content), затем итоговый текст.

**2. Скрипт куратора (задание из файла + отчёт):**

```bash
python3 scripts/curator_send_tasks_to_victoria.py --file docs/tasks/VICTORIA_TASK_ANALYZE_AND_REWRITE_VICTORIA_MDC.txt --async --max-wait 600
```

Скрипт отправит goal из файла, будет опрашивать статус до `completed` (или до `max_wait` сек), сохранит результат в `docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json` и превью в `.md`. Таймаут среды для долгих задач: не меньше 10–30 мин (CURATOR_RUNBOOK §1).

**3. Ручная отправка + опрос (как делал Cursor-агент):**  
`POST /run?async_mode=true` с телом `{goal, project_context, max_steps}` → в ответе `task_id` и `status_url` → опрашивать `GET /run/status/{task_id}` до `status=completed`.

### Единая память (LTM)

Open WebUI автоматически передаёт `user_key` в формате `openwebui-{user_id}`. Victoria сохраняет историю диалогов в Long-Term Memory для каждого пользователя.

Для общей памяти между Open WebUI и Telegram используйте один `user_key` или `session_id`.

### Подробности

См. `docs/OPENWEBUI_RAG_SETUP.md` и `docs/OPENWEBUI_SINGULARITY_15_RUNBOOK.md`

---

## 5️⃣ Telegram Bot (мобильный доступ)

### Запуск бота

```bash
# Через Docker (рекомендуется)
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-telegram-bot

# Локально
cd knowledge_os/victoria_telegram_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 bot.py
```

### Использование

1. Найдите бота в Telegram: `@YourVictoriaBotName`
2. Отправьте `/start`
3. Пишите вопросы и задачи обычным текстом

```
Вы:
Привет, Виктория! Как дела?

Victoria Bot:
Привет! Я на связи. Чем могу помочь?

Вы:
Проверь статус backend и покажи метрики

Victoria Bot:
✅ Backend работает
Метрики за последний час:
• Запросов: 1,234
• Средняя латентность: 45ms
• Ошибок: 0
```

### Команды бота

- `/start` — начать работу
- `/help` — справка
- `/status` — статус Victoria Agent
- `/clear` — очистить историю диалога

### Настройка

Файл `.env` или `knowledge_os/.env`:

```bash
# Токен бота (получить у @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# URL Victoria Agent
VICTORIA_URL=http://victoria-agent:8000  # в Docker
# или
VICTORIA_URL=http://localhost:8010  # локально

# Контекст проекта по умолчанию
DEFAULT_PROJECT_CONTEXT=atra-web-ide
```

---

## 🔧 Устранение неполадок

### Victoria Agent не запущен

```bash
# Проверка
curl http://localhost:8010/health

# Если не отвечает — запустить
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent

# Проверка логов
docker logs victoria-agent
```

### MCP сервер не работает в Cursor

```bash
# Убить старые процессы
ps aux | grep victoria_mcp_server | grep -v grep | awk '{print $2}' | xargs kill -9

# Проверка порта 8012
lsof -i :8012

# Перезапустить Cursor
# После перезапуска Cursor сам запустит MCP сервер
```

### Терминал чат не подключается

```bash
# Проверка доступности Victoria
curl http://localhost:8010/health

# Проверка переменных окружения
echo $VICTORIA_URL
echo $VICTORIA_REMOTE_URL

# Явно задать URL
VICTORIA_URL=http://localhost:8010 bash scripts/chat_victoria.sh
```

### Open WebUI не видит инструмент

1. Проверьте, что файл `configs/openwebui_ask_victoria_tool.py` импортирован
2. Проверьте Valves (настройки инструмента)
3. Убедитесь, что Victoria доступна по URL из Valves
4. Проверьте логи Open WebUI: `docker logs openwebui`

---

## 📊 Сравнение режимов

| Критерий              | Cursor MCP | Терминал чат | Терминал команда | Open WebUI | Telegram |
| --------------------- | ---------- | ------------ | ---------------- | ---------- | -------- |
| **Контекст IDE**      | ✅         | ❌           | ❌               | ❌         | ❌       |
| **Интерактивность**   | ✅         | ✅           | ❌               | ✅         | ✅       |
| **История**           | ✅         | ✅ (сессия)  | ❌               | ✅ (LTM)   | ✅ (LTM) |
| **RAG по документам** | ✅         | ✅           | ✅               | ✅         | ✅       |
| **Скорость**          | Средняя    | Быстрая      | Быстрая          | Средняя    | Средняя  |
| **Автоматизация**     | ❌         | ❌           | ✅               | ⚠️ (API)   | ⚠️ (API) |
| **Мобильный доступ**  | ❌         | ❌           | ❌               | ✅         | ✅       |
| **Красивый UI**       | ✅         | ❌           | ❌               | ✅         | ✅       |

---

## 🔍 Диагностика логов

При работе Виктории в Docker или при недоступности части сервисов в логах могут появляться следующие сообщения. Ниже — что они значат и что делать.

| Сообщение                                                                 | Значение                                                                                                                                                                                                                                                                                                                                                                                                                   | Действие                                                                                                                                                                                                              |
| ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **STRATEGIST FAILED — Falling back to cloud for planning**                | Стратег (планирование ТЗ) сначала вызывается на локальной модели (MLX/Ollama через LocalAIRouter). Если ответ пустой или начинается с ❌/⚠️ (таймаут, модель не загружена, MLX недоступен из контейнера), выполняется fallback на «облако» — далее по цепочке cursor-agent → прямой вызов Ollama. **В Docker** для вызова стратега приоритет узлов принудительно ставится на Ollama (чтобы реже срабатывал этот fallback). | Ожидаемо в Docker, если MLX из контейнера недоступен. Убедитесь, что Ollama на хосте доступен по `host.docker.internal:11434`. Для уменьшения срабатываний поднимите Ollama и модель `victoria-wisdom-v3.5` на хосте. |
| **cursor-agent not found, using direct Ollama API**                       | В контейнере нет CLI `cursor-agent` (он опционален). После `FileNotFoundError` код переходит к прямому вызову Ollama.                                                                                                                                                                                                                                                                                                      | В Docker это нормально. В логах при уровне DEBUG в Docker это сообщение не будет засорять вывод. На хосте — установите cursor-agent в PATH или игнорируйте, если хотите использовать только Ollama.                   |
| **TOOL CREATOR — Attempting to create a missing tool to fix the failure** | Ответ от модели пришёл с префиксом ❌ или ⚠️ (ошибка/неудача). Включён автономный создатель инструментов (Singularity 12.0): он пытается создать недостающий инструмент и повторить запрос. Сообщение в INFO троттлится раз в 30 с, чтобы не засорять лог при множестве параллельных запросов.                                                                                                                             | Если повторяется многократно — возможно, задача невыполнима или модель стабильно возвращает ошибку. Проверьте доступность Ollama/MLX и логи выше на предмет таймаутов/ошибок.                                         |
| **Увеличен таймаут Ollama до 1200.0с для тяжелой задачи**                 | Для запросов категории reasoning/Совет/стратег/анализ/coding таймаут Ollama увеличен до 1200 с.                                                                                                                                                                                                                                                                                                                            | Нормально для тяжёлых задач. При частых таймаутах увеличьте ресурсы или упростите запрос.                                                                                                                             |
| **ROUTE — Выбран облачный маршрут**                                       | По категории запроса (например reasoning) выбран путь, который внутри всё равно сначала пробует локальные модели, затем при неудаче — cursor-agent и Ollama.                                                                                                                                                                                                                                                               | См. `docs/WHY_LOCAL_MODELS_NOT_USED.md` для полной цепочки выбора моделей.                                                                                                                                            |

Подробнее про приоритет моделей и fallback: `docs/WHY_LOCAL_MODELS_NOT_USED.md`, `docs/MASTER_REFERENCE.md` (STRICT_LOCAL, порты).

### Кто отслеживает ошибки контейнеров в Docker

В Docker за ошибки контейнеров и сервисов отвечает цепочка:

1. **Service Monitor** (внутри контейнера Victoria) — проверяет по HTTP здоровье Victoria, Backend, MLX, Frontend; при падении публикует **SERVICE_DOWN** в Event Bus.
2. **Victoria** подписана на SERVICE_DOWN: пытается перезапустить сервис (SelfCheckSystem); при неудаче передаёт задачу на диагностику **Елене (Monitor)**.
3. **Ответственный эксперт:** **Елена** (Monitor) — логи, алерты, Prometheus, Grafana; при необходимости привлекается **Сергей** (DevOps) для перезапуска/инфраструктуры.

Назначение зафиксировано в `configs/experts/team.md` (§ «Ответственный за ошибки контейнеров»).

---

## 🎓 Лучшие практики

### Для работы с кодом

- **Используйте Cursor MCP** — контекст открытых файлов и git status автоматически передаётся Виктории
- Явно упоминайте файлы: "Проверь файл backend/app/main.py"

### Для вопросов и диалога

- **Терминал чат** — быстрый интерактивный режим
- **Open WebUI** — если нужен красивый интерфейс и RAG по документам

### Для автоматизации

- **Терминал команда** — в скриптах CI/CD, мониторинге, автоматических проверках
- **API** — для интеграции с внешними системами

### Для мобильного доступа

- **Telegram** — уведомления, быстрые ответы на ходу

---

## 📚 Дополнительные ресурсы

- `docs/VICTORIAATRA_HOW_TO_CALL.md` — краткая справка по MCP инструментам
- `docs/VICTORIA_TERMINAL_CHAT_FLOW.md` — как работает терминальный чат
- `docs/OPENWEBUI_RAG_SETUP.md` — настройка Open WebUI с RAG
- `docs/MASTER_REFERENCE.md` — библия проекта (архитектура, команда, изменения)
- `VICTORIA.md` — полная документация по Victoria Agent

---

**Создано:** 2026-03-06  
**Автор:** Victoria Team Lead + Cursor AI Assistant  
**Версия:** 1.0
