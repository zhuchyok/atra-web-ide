# Victoria постоянно вылетает — причины и исправления

**Назначение:** зафиксировать выявленные причины перезапусков victoria-agent и меры.

**Перезапуск вручную:** `docker compose -f knowledge_os/docker-compose.yml restart victoria-agent`. Полный старт ~30–60 с.

---

## 1. Ложный «Victoria Agent: down» (исправлено 2026-02-08)

**Симптом:** В логах сразу после старта: «Статус Victoria Agent: unknown → down», «Обработка падения сервиса: Victoria Agent», «Сервис перезапущен: Victoria Agent». Остальные сервисы тоже помечаются down (Backend, Frontend, MLX и т.д.).

**Причина:** Service Monitor (запущен внутри контейнера Victoria) проверяет здоровье по URL из списка по умолчанию. Для «Victoria Agent» был задан **endpoint=http://localhost:8010**. Внутри контейнера Victoria слушает порт **8000** (снаружи маппинг 8010→8000). Проверка localhost:8010 изнутри контейнера не доходит до процесса → ConnectError → статус DOWN.

**Исправление:**

- В **service_monitor.py** для «Victoria Agent» endpoint берётся как `http://127.0.0.1:{VICTORIA_PORT}`. В контейнере задано `VICTORIA_PORT=8000` → проверка идёт на localhost:8000, сам себя Victoria видит как UP.
- Перед первым проходом цикла мониторинга — задержка по умолчанию **50 с** (**SERVICE_MONITOR_INITIAL_DELAY**, диапазон 25–120): время на подъём HTTP Victoria (25–40 с), развёртывание, запас на загрузку моделей при первом запросе. **У каждой модели своё время** (1–4B — секунды, 70B/104B — минуты); при тяжёлых моделях увеличивать задержку (см. [MODEL_TIMING_REFERENCE.md](MODEL_TIMING_REFERENCE.md)).
- При DOWN по HTTP добавлено логирование причины: **ConnectError** или таймаут, с URL — в логах видно, почему сервис помечен как down (`🔌 Victoria Agent недоступен (ConnectError): ...`).
- Для «Veronica Agent» при работе в контейнере (VICTORIA_PORT=8000) endpoint задаётся как `http://veronica-agent:8000` (сеть Docker).
- В **victoria_event_handlers.py** при событии SERVICE_DOWN для сервиса «Victoria Agent» перезапуск **пропускается** (не пытаемся перезапустить себя).

**Итог:** Ложные срабатывания «сам себя down» и каскад событий перезапуска устранены.

---

## 2. Много рестартов (RestartCount 15+): OOM

**Симптом:** `docker inspect victoria-agent --format '{{.RestartCount}}'` показывает 10–20 и более. Контейнер перезапускается по политике `restart: always`.

**Вероятная причина:** **OOM Kill (exit code 137)**. При старте Victoria загружает много компонентов (51 skill, ReAct, Event Bus, File Watcher, Service Monitor, RAG preload с эмбеддингами). Пик потребления памяти — в момент старта; при нехватке памяти Docker/ядро убивает процесс (SIGKILL → 137).

**Что делать:**

1. **Проверить:** `docker inspect victoria-agent --format '{{.State.OOMKilled}}'` после падения (до следующего рестарта можно смотреть последний контейнер в истории).
2. **Увеличить память для Docker** (Docker Desktop → Settings → Resources → Memory) или снять/увеличить лимит для контейнера. На **Mac Studio** рекомендуется 10–14 GB для Docker при 64–128 GB RAM хоста (см. [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md)).
3. **Снизить нагрузку при старте:** отключить часть мониторинга или предзагрузку RAG на время проверки:
   - `RAG_PRELOAD_TYPICAL_QUERIES=false`
   - `SERVICE_MONITOR_ENABLED=false` или `ENABLE_EVENT_MONITORING=false`
4. См. также **ORCHESTRATOR_137_AND_OLLAMA.md** (OOM, причины 137) и **LIVING_ORGANISM_PREVENTION.md**.

**Режим лёгкого старта (если контейнер в цикле рестартов):** задать в `knowledge_os/docker-compose.yml` для сервиса `victoria-agent` в `environment:`:

```yaml
RAG_PRELOAD_TYPICAL_QUERIES: "false"
SERVICE_MONITOR_ENABLED: "false"
ENABLE_EVENT_MONITORING: "false"
```

Затем `docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent --force-recreate`. После стабилизации можно вернуть `true` и перезапустить.

---

## 3. Падение при старте: USE_ELK=true и elk_handler (no running event loop)

**Симптом:** Контейнер перезапускается (RestartCount растёт). В логах множество `Traceback`, `RuntimeError: no running event loop` в `elk_handler.py` при `emit()`.

**Причина:** При **USE_ELK=true** в контейнере Victoria при старте к логгеру подключается ELK handler. Во время инициализации (до запуска Uvicorn event loop) любой вызов `logger.info()` вызывает `emit()` → `asyncio.create_task()` → нет running loop → падение процесса. Docker перезапускает контейнер по политике restart.

**Исправление:**

1. **В docker-compose** для `victoria-agent` задать **USE_ELK: "false"** (или не задавать USE_ELK в .env). Затем: `docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent --force-recreate`.
2. В коде **knowledge_os/app/elk_handler.py** при flush по размеру буфера вызывать `create_task` только если есть running loop: `get_running_loop()` в try, при RuntimeError — не падать (буфер отправится позже). После этого при необходимости можно снова включить USE_ELK.

**Итог:** Пока ELK не нужен — держать USE_ELK=false; иначе обновить образ с исправленным elk_handler и пересоздать контейнер.

---

## 4. Sync /run таймаут и пустой ответ; опрос /run/status не отвечает

**Симптом:** POST /run (sync) — таймаут 90+ с или пустое тело (connection reset, http_code 000). GET /run/status/{task_id} при async_mode — тоже пустой ответ или connection reset.

**Возможные причины:**

1. **Долгая задача блокирует event loop** — один воркер Uvicorn занят выполнением задачи (LLM, инструменты), запросы на /health или /run/status не обрабатываются вовремя или обрываются.
2. **Перезапуск контейнера** во время выполнения — при первом тяжёлом запросе контейнер падает (OOM, исключение), все соединения обрываются.

**Что делать:**

- Для **задач 3 и 4** (список файлов, «что умеешь») использовать **async_mode**: `POST /run?async_mode=true` → 202 + task_id, затем опрос `GET /run/status/{task_id}`. Скрипт: `bash scripts/run_victoria_tasks_3_and_4_async.sh`.
- Убедиться, что Victoria стабильна перед прогоном: `/health` 200, контейнер не в цикле рестартов (см. §1–3). При нестабильности — устранить причину (USE_ELK=false, память, мониторинг).
- Если опрос статуса всё равно не возвращает ответ — выполнение задачи может блокировать процесс; в перспективе вынести выполнение в отдельный воркер/процесс.

---

## 4.1. Async-задачи долго в status=running (2026-02-09)

**Симптом:** POST /run?async_mode=true возвращает 202 и task_id, но GET /run/status/{task_id} долго показывает status=running и за время опроса не переходит в completed.

**Причина (пошагово):**

1. **Код записи в store корректен** — в `_run_task_background` при завершении выставляется `store["status"] = "completed"` (или "failed" в except); done_callback при исключении тоже выставляет failed. Бага с «не пишется completed» нет.
2. **Задача реально выполняется дольше окна опроса.** Цепочка: маршрутизация (task_type) → либо делегирование в Veronica (таймаут 90 с, DELEGATE_VERONICA_TIMEOUT), либо Victoria Enhanced, либо `agent.run()`. В `agent.run()` — несколько вызовов LLM: understand_goal, plan, затем шаги (каждый шаг — один запрос к Ollama/MLX). **У каждой модели своё время** (см. [MODEL_TIMING_REFERENCE.md](MODEL_TIMING_REFERENCE.md)): один вызов 30–300+ с для тяжёлых моделей; одна задача = 3–10+ вызовов → минуты.
3. **«Список файлов»** сначала идёт в Veronica (простой запрос); если Veronica недоступна или таймаут — fallback в agent.run(). **«Что умеешь»** идёт в enhanced/agent.run. Оба могут упереться в долгие вызовы локальной модели.

**Что сделано:**

- В **run_victoria_tasks_3_and_4_async.sh** окно опроса увеличено до **60 опросов по 10 с** (до 600 с на задачу); в выводе опроса выводится **stage** (queued / delegate_veronica / enhanced_solve / agent_run), чтобы видеть, на каком этапе задача.
- Скрипт **scripts/measure_ollama_response_time.sh** — замер времени одного запроса к Ollama (и при наличии MLX): даёт ориентир, сколько занимает один вызов LLM на вашей машине.
- Рекомендация: для тяжёлых моделей (32B+) смотреть MODEL_TIMING_REFERENCE и при необходимости увеличивать число опросов или интервал в скрипте (например 90\*10 с).

**Проверка:** запустить `bash scripts/measure_ollama_response_time.sh`, затем `bash scripts/run_victoria_tasks_3_and_4_async.sh`; в логах смотреть stage — если долго agent_run, задача ждёт ответов модели.

**Наблюдение (2026-02-09):** в логах Victoria один вызов LLM (understand_goal, phi3.5:3.8b через host.docker.internal:11434) занял **122.95 с**. Один шаг = 1–2 мин типично; задача из нескольких шагов может занимать 5–10+ мин. Окно опроса 60×10 с рассчитано на это; вывод опросов (status, stage) перенесён в stderr, чтобы не теряться при `S4=$(poll_until_done ...)`.

---

## 4.2. 503 «All connection attempts failed» при опросе /run/status (2026-02)

**Симптом:** Open WebUI или тест `test_ask_victoria_chain.sh`: POST ask-victoria → 202, затем через 1–2 мин ответ 503 с текстом «Victoria недоступна (нет связи)» или в логах бэкенда `client error: All connection attempts failed`. Иногда один запрос проходит (200), следующий — 503.

**Разбор причин:**

1. **RestartCount Victoria высокий** — у контейнера `victoria-agent` много рестартов (десятки). Каждый рестарт = 30–60 с недоступности; store задач в памяти Victoria при рестарте теряется.
2. **Во время опроса Victoria уходит в рестарт** — бэкенд держит цикл GET /run/status каждые 8 с; если в этот момент контейнер Victoria перезапускается (OOM, краш, политика restart), следующий GET даёт ConnectError → исключение в `run()` → 503.
3. **Сеть:** бэкенд и Victoria в одной сети (atra-network), имя `victoria-agent` резолвится; проблема не в DNS, а в недоступности процесса во время рестарта.

**Что сделано (бэкенд):**

- В **backend/app/services/victoria.py** в цикле опроса GET /run/status добавлены **ретраи при сбоях соединения**: при `ConnectError`, `TimeoutException`, `RemoteProtocolError` — до 5 попыток с паузой 12 с перед тем как вернуть 503. Краткий рестарт Victoria (30–60 с) может «переживаться» без немедленного 503.
- При ответе Victoria **404** на GET /run/status (задача не найдена — типично после рестарта, store в памяти потерян) бэкенд возвращает понятную ошибку: «Task lost (Victoria may have restarted). Please retry your request.»

**Рекомендации:**

- Снизить частоту рестартов Victoria: см. §1–3 (USE_ELK=false, память Docker, при необходимости RAG_PRELOAD/SERVICE_MONITOR в false), §2 (OOM).
- После деплоя правок бэкенда — пересобрать образ и перезапустить контейнер backend.

---

## 4.3. NameError user_key при делегировании экспертам (MONSTER) (2026-02)

**Симптом:** В логах Victoria при выполнении плана с делегированием: `❌ [MONSTER] Ошибка выполнения для &lt;Имя&gt;: EXCEPTION: NameError: name 'user_key' is not defined`. Повторяется для нескольких экспертов (Константин, Василий, Тимофей, Андрей, Татьяна и др.).

**Причина:** В **ai_core.run_smart_agent_async_impl** переменные `user_key` и `project_context` задавались только внутри блока `if is_coding_task and not is_critical`. При вызове из **execute_assignments** (category=orchestrator_assignment) подзадачи часто не попадают в этот блок (нет ключевых слов кодинга в формулировке), при этом episodic memory (get_episodes) вызывается только в этом блоке — но в других путях мог использоваться user_key, либо блок выполнялся в ином порядке. Фактически при части сценариев user_key не определялся до использования.

**Исправление:** В начале run_smart_agent_async_impl заданы значения по умолчанию: `user_key = session_id or "orchestrator"`, `project_context = os.getenv("MAIN_PROJECT", "atra-web-ide")`. Таким образом, при вызове из execute_assignments без session_id используется user_key="orchestrator", ошибка не возникает.

**Итог:** После обновления кода в knowledge_os и пересборки образа victoria-agent ошибки MONSTER из-за user_key должны исчезнуть.

---

## 4.4. OOM (Out of Memory) при старте или тяжелых задачах (2026-02)

**Симптомы:** `RestartCount` растет, в `docker events` ошибка `container oom` (exitCode 137), хотя `docker inspect` может показывать `OOMKilled=false`.

**Причина:** Контейнер `victoria-agent` потребляет 6+ ГБ в простое и может скачкообразно расти при инициализации ReAct или делегировании. Если лимит в Docker Desktop (например, 12 ГБ) ниже лимита в `docker-compose.yml` (16 ГБ), Docker убивает процесс.

**Решение:**

1. Сняты жесткие лимиты `mem_limit` в `knowledge_os/docker-compose.yml` (пусть Docker Desktop сам управляет ресурсами).
2. Отключен прогрев тяжелых моделей при старте (`VICTORIA_WARMUP_EXTRA_MODELS=""`), что снижает пиковую нагрузку на CPU/RAM при запуске.

---

## 5. Улучшения в цепочке Backend -> Victoria (2026-02)

- **Polling Retries:** В `backend/app/services/victoria.py` добавлен внутренний цикл ретраев (5 попыток по 12 сек) для `GET /run/status`. Это позволяет пережить кратковременный рестарт Victoria без падения всего запроса.
- **404 Handling:** Если Victoria вернула 404 при опросе статуса (задача потеряна из-за рестарта), бэкенд возвращает четкую ошибку: "Задача потеряна (Victoria могла перезапуститься)".
- **Timeout Fix:** Исправлен конструктор `httpx.Timeout` (требует явного указания всех 4 параметров или одного дефолта).

---

## 6. Стабильность при нагрузке: что сделано (2026-02-09)

**Проблема:** при небольшой нагрузке Victoria вылетает или перестаёт отвечать (connection reset, пустой ответ).

**Внесённые изменения:**

1. **Обработка исключений в фоновой задаче**
   - У фоновой задачи (`asyncio.create_task(_run_task_background(...))`) добавлен **done_callback**: необработанное исключение логируется, в `_run_task_store` для задачи выставляется `status=failed`, `error=...`. Это предотвращает «тихий» краш процесса из-за необработанного исключения в задаче.
   - В `_run_task_background` добавлена обработка **asyncio.CancelledError** и **BaseException**: задача помечается failed, исключение логируется; BaseException пробрасывается дальше (корректное завершение/отмена).

2. **Рекомендация по режиму запросов**
   - **Sync** `POST /run` (без `async_mode`) держит единственный воркер занятым на время выполнения (LLM, инструменты). Пока воркер занят, запросы к `/health` и `/run/status` не обрабатываются → клиенты получают таймаут или connection reset.
   - **Решение:** для любых нетривиальных запросов использовать **async_mode=true**: `POST /run?async_mode=true` → сразу 202 + task_id, результат забирать через `GET /run/status/{task_id}`. Тогда воркер не блокируется надолго, /health и опрос статуса остаются отвечающими.

3. **Uvicorn**
   - Запуск с явным числом воркеров: `UVICORN_WORKERS` (по умолчанию 1). При одном воркере общий store для `/run/status` корректен; при нескольких воркерах потребуется общий store (например Redis).

4. **Чек-лист при вылетах**
   - USE_ELK=false в окружении контейнера (см. §3).
   - Достаточно памяти для Docker (рекомендуется 4GB+ для Victoria + Ollama/MLX); при OOM — см. §2.
   - Для длинных задач — только async_mode; не полагаться на долгий sync /run без таймаута на клиенте.

- **Mac Studio:** учёт характеристик и загрузки — [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md) (память Docker, MAX_CONCURRENT_VICTORIA, async_mode).

5. **Lifespan: зависание после «Database pool создан» (2026-02-08)**
   - **Симптом:** в логах последнее сообщение — «✅ Knowledge OS Database pool создан»; дальше нет «Загружено N экспертов», «Реестр проектов загружен», «Uvicorn running» — процесс не выходит из lifespan.
   - **Причина:** блокировка на `await agent._load_expert_team()` (SELECT из `experts`) или на `await get_projects_registry()` (подключение к БД/запрос к `projects`) без таймаутов; при медленной/недоступной БД или блокировке — старт «висит».
   - **Исправление:** в **victoria_server.py** lifespan:
     - предзагрузка экспертов обёрнута в **asyncio.wait_for(..., timeout)** — по умолчанию **30 с** (учёт холодной БД, развёртывания, запаса); задаётся **VICTORIA_STARTUP_EXPERTS_TIMEOUT**; при таймауте старт продолжается без экспертов;
     - загрузка реестра проектов — по умолчанию **20 с** (**VICTORIA_STARTUP_REGISTRY_TIMEOUT**); при таймауте — fallback (env/hardcoded);
     - у **asyncpg.create_pool** — **command_timeout** по умолчанию **25** (**VICTORIA_DB_POOL_COMMAND_TIMEOUT**);
     - перед **yield** — лог «Lifespan startup завершён, Uvicorn переходит в режим приёма запросов».
   - Если в логах таймаут экспертов/реестра — проверить БД (knowledge_postgres), сеть Docker, таблицы `experts` и `projects`. На медленном железе или при холодном старте можно увеличить таймауты через env.

---

## 6. Падение Python на хосте при нехватке памяти (2026-02-10)

**Симптом:** Приложение «Python» неожиданно завершает работу (диалог macOS или процесс Cursor/IDE). Часто при активной работе с Victoria (редактирование victoria_enhanced.py, прогон куратора, агенты).

**Вероятная причина:** Давление памяти на хосте. Одновременно работают:

- **Ollama** — несколько процессов, суммарно 25–35+ ГБ при загруженных моделях;
- **Docker** — контейнеры (Victoria, Veronica и др.) — 10–15 ГБ;
- **Python** — 5–7 ГБ (IDE, агенты, скрипты).

При 128 ГБ RAM использование под 104 ГБ и своп 2–3 ГБ ядро может убивать процессы (OOM → exit 137) или Python падает при нехватке выделения.

**Что делать:**

1. **Проверить память:** Мониторинг системы (Activity Monitor) — вкладка «Память». Обратить внимание на «Используемая память», «Своп», процессы ollama и Python.
2. **Выгрузить неиспользуемые модели Ollama:** `ollama list` → для редко используемых моделей не держать в памяти (после теста вызвать keep_alive=0 или перезапустить Ollama). Это освобождает десятки ГБ.
3. **Перед тяжёлыми прогонами куратора** по возможности закрыть лишние приложения и не загружать тяжёлые модели Ollama без необходимости.
4. **Если падает контейнер Victoria:** см. §2 (OOM в контейнере). Если падает локальный Python (IDE/скрипт) — увеличить свободную память хоста за счёт Ollama/Docker.

**Связь с куратором:** При прогоне куратора (run_curator_scheduled.sh) одновременно работают Victoria, опционально Veronica, Ollama/MLX. При нехватке памяти возможны connection reset или падение процесса. Рекомендация: следить за свопом; при стабильных падениях — снизить число одновременных задач или выгружать модели между прогонами. См. [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md), [CURATOR_LIST_FILES_FAILURES.md](curator_reports/CURATOR_LIST_FILES_FAILURES.md).

---

## 7. Ссылки

- Замер времени одного ответа модели: `scripts/measure_ollama_response_time.sh`
- Замер **каждой** модели: `scripts/measure_all_ollama_models.sh` (Ollama) → tmp/ollama_model_timings._; `scripts/measure_all_models_ollama_mlx.py` (Ollama + MLX, таймауты по размеру + буфер на запуск) → tmp/model_timings_ollama_mlx._
- Время по моделям (загрузка, один вызов): [MODEL_TIMING_REFERENCE.md](MODEL_TIMING_REFERENCE.md)
- Service Monitor (внутри Victoria): `knowledge_os/app/service_monitor.py` (\_get_default_services, VICTORIA_PORT)
- Обработчик SERVICE_DOWN: `knowledge_os/app/victoria_event_handlers.py` (handle_service_down, skip self)
- Оркестратор 137 и OOM: [ORCHESTRATOR_137_AND_OLLAMA.md](ORCHESTRATOR_137_AND_OLLAMA.md)
- Чеклист: VERIFICATION_CHECKLIST_OPTIMIZATIONS §3, §5
- Прогон задач 3–4 (async): scripts/run_victoria_tasks_3_and_4_async.sh
- Mac Studio: загрузка и настройки: [MAC_STUDIO_LOAD_AND_VICTORIA.md](MAC_STUDIO_LOAD_AND_VICTORIA.md)
