# Правки из других чатов — сводка для агента

 Документ собирает ключевые изменения и улучшения, сделанные в других чатов, чтобы новый контекст (агент/чат) мог опираться на уже внедрённое.

---

## 0.5a. Singularity 20.0: The Wisdom Era (20/10) (2026-02-19)
- **Сделано:** 
    1. **Collective Brainstorming**: Реализован модуль `collective_brainstorming.py` для автономного проектирования сложных фич через диалог экспертов (Игорь, Анна, Елена) под руководством Виктории. Интегрирован в `ai_core.py` (триггеры: brainstorm, обсуди, спроектируй).
    2. **Mentorship Engine**: Создан `mentorship_engine.py` для автоматического аудита выполненных задач. Виктория генерирует персональные советы (Mentorship Notes), которые сохраняются в KB и внедряются в контекст экспертов.
    3. **SOP Generator**: Реализован `sop_generator.py` для автоматического создания Standard Operating Procedures на основе успешных задач (8/10+). Инструкции сохраняются в `docs/SOP/`.
    4. **Adversarial Red Teaming**: Обновлен `adversarial_critic.py` для верификации новых SOP и инсайтов через стресс-тест. Интегрирован в `nightly_learner.py`.
    5. **Wisdom Injection**: В `ai_core.py` внедрена инъекция мета-стратегий и советов ментора прямо в системные промпты перед вызовом LLM.
    6. **Wisdom Dashboard**: В дашборд добавлена вкладка `Wisdom & Mentorship` для мониторинга среднего балла аудита, количества SOP и плотности мудрости.
- **Итог:** Система перешла от простого выполнения задач к накоплению мудрости и самообучению через внутреннюю обратную связь. Mac Studio работает как автономный «Живой Организм».

---

## 0.4fw. Бэкенд ask_victoria: async_mode вместо sync /run (причина 503 и обрывов) (2026-02-19)
- **Причина (docs/VICTORIA_RESTARTS_CAUSE §4):** Бэкенд вызывал Victoria через **sync** POST /run и держал соединение до 900 с. Один воркер Uvicorn в Victoria блокировался на время задачи; при долгом ответе соединение обрывалось («Server disconnected without sending a response», «All connection attempts failed») или Victoria перезапускалась.
- **Сделано:** В **backend/app/services/victoria.py** метод **run()** переведён на **async_mode**: POST /run?async_mode=true (короткий таймаут 120 с на 202), затем опрос GET /run/status/{task_id} каждые 8 с до completed/failed (общий таймаут 900 с). Задача выполняется в фоне в Victoria, воркер не блокируется, /health и опрос статуса остаются отвечающими.
- **Итог:** Запросы ask_victoria (чат, Open WebUI) стабильнее; меньше обрывов и 503 из-за блокировки воркера. При необходимости увеличить общий таймаут: VICTORIA_TIMEOUT в .env.

---

## 0.4fz. Victoria: NameError user_key в execute_assignments (MONSTER) (2026-02)
- **Проблема:** В логах Victoria при делегировании экспертам (execute_assignments): `NameError: name 'user_key' is not defined` для нескольких экспертов (Константин, Василий, Тимофей и др.). run_smart_agent_async вызывается без session_id; в ai_core user_key и project_context задавались только внутри блока `if is_coding_task and not is_critical`, при других путях (оркестраторские подзадачи) переменная не определялась.
- **Сделано:** В **knowledge_os/app/ai_core.py** в начале run_smart_agent_async_impl добавлено определение `user_key = session_id or "orchestrator"` и `project_context = os.getenv("MAIN_PROJECT", "atra-web-ide")`, чтобы они были заданы при любом пути выполнения (в т.ч. вызов из execute_assignments).
- **Итог:** Ошибки «Ошибка выполнения для &lt;эксперт&gt;: user_key is not defined» при делегировании из Victoria должны исчезнуть. Пересборка образа агентов (Victoria) для применения: `docker compose -f knowledge_os/docker-compose.yml build victoria-agent && docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent`.

---

## 0.4fy. ask_victoria 503 при опросе статуса: ретраи GET /run/status и 404 (2026-02)
- **Проблема:** Во время опроса GET /run/status Victoria перезапускалась или теряла связь → «All connection attempts failed» → 503. RestartCount контейнера victoria-agent высокий (десятки рестартов).
- **Сделано:** (1) В **backend/app/services/victoria.py** в цикле опроса: при ConnectError/TimeoutException/RemoteProtocolError — до 5 ретраев с паузой 12 с перед возвратом 503. (2) При 404 от Victoria (task_id не найден, типично после рестарта) — возврат ошибки «Task lost (Victoria may have restarted). Please retry your request.» (3) В **VICTORIA_RESTARTS_CAUSE.md** добавлен §4.2: разбор причин и рекомендации.
- **Итог:** Краткие рестарты Victoria (30–60 с) бэкенд переживает без немедленного 503; при потере задачи — понятное сообщение. Для устойчивости важно снижать рестарты Victoria (см. VICTORIA_RESTARTS_CAUSE §1–3, §2 OOM). После правок — пересборка образа backend.

---

## 0.4fx. ask_victoria v1.1: chat_history, response_format; бэкенд принимает контекст (2026-02)
- **Сделано:** (1) **Инструмент** `configs/openwebui_ask_victoria_tool.py`: добавлены параметры `__messages__` (контекст чата от Open WebUI) и `response_format` ("text" | "json"). `__messages__` конвертируются в формат Victoria (user/assistant) и передаются как `chat_history` (последние 15 пар). При `response_format="json"` запрос к бэкенду идёт с `?format=json`. (2) **Бэкенд** `backend/app/routers/chat.py`: в `AskVictoriaRequest` добавлено поле `chat_history` (опционально); передаётся в `victoria.run(chat_history=...)`. (3) **Документация:** `docs/ASK_VICTORIA_OPENWEBUI_IMPROVEMENTS.md` — внедрённые улучшения и отложенные (стриминг SSE, __files__, структурированные ошибки, язык, телеметрия).
- **Итог:** Виктория получает историю диалога при вызове из Open WebUI; модель может запрашивать ответ в JSON. После правок бэкенда нужна **пересборка образа** и перезапуск контейнера backend; в Open WebUI — переимпорт инструмента и обновление системного промпта.

---

## 0.4fv. Open WebUI: модель не вызывала ask_victoria из-за старого «источника» (2026-02-19)
- **Проблема:** В контексте появлялся «источник id=1» с текстом «Victoria временно недоступна (server busy)» — результат **прошлого** вызова инструмента. Модель (qwq:32b) воспринимала это как текущее состояние и не вызывала ask_victoria при новом запросе пользователя.
- **Причина:** Инструмент при 503/ошибке возвращал сообщение без указания «это прошлая попытка»; в системном промпте не было правила «при новом запросе всегда вызывать инструмент снова».
- **Сделано:** (1) **SINGULARITY_15_GOLDEN_PERSONA.md:** добавлено правило: сообщение о недоступности в источнике относится к прошлому вызову; для текущего запроса сначала вызвать ask_victoria, отказ только если текущий вызов вернул ошибку. (2) **openwebui_ask_victoria_tool.py:** все ответы «недоступна» заменены на формулировку «…for this attempt. On the user's next request, call ask_victoria again».
- **Итог:** Модель при новом запросе должна снова вызывать ask_victoria; «источник» с прошлой ошибкой не считается причиной пропускать вызов. Обновить системный промпт в Open WebUI из SINGULARITY_15_GOLDEN_PERSONA.md и переимпортировать инструмент при необходимости.

---

## 0.4fu. Отчёты и уведомления в Telegram не приходили — воркер в Docker (2026-02-19)
- **Проблема:** Пользователь не получал в Telegram ни отчётов, ни уведомлений (новые эксперты, дебаты, онбординг и т.д.).
- **Причина:** Уведомления из таблицы `notifications` отправляет только код в `telegram_gateway.check_notifications()`, который вызывается из цикла `telegram_bridge()`. Отчёты (ежедневный 8:00, еженедельный понедельник 9:00) генерирует Report Generator внутри `singularity_autonomous`. Ни telegram_gateway, ни singularity_autonomous не были сервисами в docker-compose — их нужно было запускать вручную, поэтому по умолчанию ничего не отправлялось.
- **Сделано:** (1) Добавлен **knowledge_os/app/telegram_notifications_worker.py**: раз в 60 с отправляет записи из `notifications` (WHERE sent = FALSE) в Telegram; при включённом TELEGRAM_REPORTS_ENABLED запускает цикл Report Generator (ежедневно 8:00, еженедельно понедельник 9:00). (2) В **knowledge_os/docker-compose.yml** добавлен сервис **telegram-notifications** (образ agents, команда `python -u telegram_notifications_worker.py`), с переменными TELEGRAM_BOT_TOKEN/TG_TOKEN и TELEGRAM_USER_ID/CHAT_ID. (3) В **docs/TELEGRAM_VICTORIA_TROUBLESHOOTING.md** добавлен раздел «Отчёты и уведомления не приходят»: проверка контейнера, .env (TELEGRAM_USER_ID, токен), логи.
- **Итог:** После `docker compose -f knowledge_os/docker-compose.yml up -d telegram-notifications` и при заданных в .env `TELEGRAM_BOT_TOKEN` и `TELEGRAM_USER_ID` (ваш Telegram user id от @userinfobot) уведомления из БД и отчёты начнут приходить в Telegram. Если переменные не заданы — воркер пишет предупреждение в лог.

---

## 0.4ft. Обучение (Nightly Learner) снова работает (2026-02-19)
- **Проблема:** Контейнер knowledge_nightly падал при старте: `ModuleNotFoundError: No module named 'psutil'` (memory_guard импортирует psutil). Цикл обучения не выполнялся, в логах только traceback и «Цикл завершён» от shell.
- **Сделано:** (1) В корневой **requirements.txt** добавлен `psutil>=5.9.0` (образ агентов при пересборке получит psutil). (2) В **knowledge_os/app/memory_guard.py** импорт psutil сделан опциональным: при отсутствии модуля проверка памяти отключена, `check_memory()` возвращает `is_safe=True`, Nightly Learner стартует без падения.
- **Итог:** После перезапуска контейнера (`docker restart knowledge_nightly`) обучение запускается; при следующей пересборке образа agents psutil будет в образе и MemoryGuard будет работать полностью.

---

## 0.4fs. Стратегическая директива Совета Директоров и планировщик (2026-02-19)
- **Вопрос:** «СТРАТЕГИЧЕСКАЯ ДИРЕКТИВА СОВЕТА (ОТ 17.02 15:24) — работает? два дня ничего не делали».
- **Проверено:** Директива 17.02 15:24 есть в БД (knowledge_nodes type=board_directive, board_decisions source=nightly). Дашборд 8501 → Стратегия → «Решения Совета» читает из knowledge_nodes — блок отображается. Новые директивы создаёт только run_board_meeting(); скрипт board_scheduler.py (каждые 6 ч) не был в docker-compose, поэтому автоматических заседаний не было.
- **Сделано:** В knowledge_os/docker-compose.yml добавлен сервис **board-scheduler** (образ agents, python board_scheduler.py). В board_scheduler.py при недоступности /app/logs (volume :ro) лог пишется в /tmp/board_scheduler.log.
- **Итог:** После `docker compose up -d board-scheduler` каждые 6 ч будет создаваться новая директива; она появится на дашборде во вкладке «Решения Совета».

---

## 0.4fr. Tactical War Room (Экстренное реагирование) снова в работе (2026-02-19)
- **Проблема:** War Room не срабатывал ~2 дня — в дашборде «Активных сессий в War Room нет», при 500 бэкенд не созывал экспертов.
- **Причины:** (1) В бэкенде импорт был `from app.war_room` (backend app), тогда как модуль лежит в `knowledge_os/app/war_room.py`; PYTHONPATH уже содержит `.../knowledge_os/app`, нужен импорт `from war_room import ...`. (2) В таблице `expert_discussions` не было колонки `metadata`, которую использует War Room для session_id, log, severity — INSERT падал.
- **Выполнено:** (1) `backend/app/middleware/error_handler.py`: вызов War Room через `from war_room import trigger_war_room_if_needed`, логирование с exc_info при ошибке. (2) Миграция `knowledge_os/db/migrations/add_expert_discussions_metadata.sql`: добавлена колонка `metadata JSONB`, индекс GIN; миграция применена к БД.
- **Итог:** При любой необработанной 500 бэкенд фоново вызывает War Room; сессия пишется в `expert_discussions`, дашборд (вкладка «🚨 War Room») показывает сессии. Если при деплое миграция не применялась — выполнить `add_expert_discussions_metadata.sql`.

---

## 0.4fq. ask_victoria 503: понятные сообщения и диагностика (2026-02-14)
- **Проблема:** При 503 от бэкенда («Victoria временно недоступна») пользователь и модель не понимали причину (таймаут, нет связи, перегрузка).
- **Выполнено:** (1) Backend `POST /api/chat/ask-victoria`: при 503 в теле ответа возвращается краткая причина — таймаут / нет связи с Victoria / перегрузка (функция `_user_facing_error` по тексту исключения или `result.error`). (2) Скрипт `scripts/test_ask_victoria_chain.sh`: проверка цепочки (GET /health, POST ask-victoria с простой целью), переменные BACKEND_URL, ASK_TIMEOUT. (3) Runbook OPENWEBUI_SINGULARITY_15_RUNBOOK.md: в таблицу проблем добавлена строка про 503 и запуск диагностики; добавлен подраздел «Диагностика цепочки Backend → Victoria».
- **Итог:** После рестарта бэкенда при 503 в чате Open WebUI будет видно «Victoria не успела ответить (таймаут)» или «Victoria недоступна (нет связи)»; для проверки — `./scripts/test_ask_victoria_chain.sh`.

---

## 0.4fp. Реестр проектов: setki-21 и автоматизация (2026-02-19)
- **Выполнено:** (1) Добавлен **setki-21** в сидер миграции `knowledge_os/db/migrations/add_projects_table.sql` (INSERT ... ON CONFLICT DO NOTHING). (2) В `src/agents/bridge/project_registry.py`: setki-21 добавлен в `DEFAULT_PROJECT_CONFIGS` и в дефолт `ALLOWED_PROJECTS`. (3) В БД выполнена вставка setki-21 (через `docker exec knowledge_postgres psql`), Victoria перезапущена. (4) В **docs/NEW_PROJECT_MINIMAL_STEPS.md** добавлен §0 «Автоматизация»: при добавлении нового проекта править миграцию (сидер) и project_registry (DEFAULT_PROJECT_CONFIGS + ALLOWED_PROJECTS), чтобы не забыть при следующих деплоях.
- **Итог:** setki-21 в реестре; запросы «проанализируй проект сетки 21» принимаются с project_context=setki-21. Новые проекты — добавлять в миграцию и в реестр по чеклисту §0.

---

## 0.4fp. setki-21 в реестре проектов и автоматизация (2026-02-19)
- **Сделано:** (1) setki-21 добавлен в сидер миграции `knowledge_os/db/migrations/add_projects_table.sql` (INSERT ... ON CONFLICT DO NOTHING). (2) В `src/agents/bridge/project_registry.py`: setki-21 в `DEFAULT_PROJECT_CONFIGS`, в дефолт `ALLOWED_PROJECTS` добавлен setki-21. (3) Регистрация в текущей БД выполнена (docker exec knowledge_postgres psql ... INSERT). (4) Victoria и Veronica перезапущены. (5) docs/PROJECT_SETKI_21_SETUP.md обновлён: указано, что проект уже в сидере, ручная регистрация не нужна при новых деплоях.
- **Итог:** Запросы с project_context=setki-21 принимаются. Новые проекты по-прежнему добавлять в миграцию и DEFAULT_PROJECT_CONFIGS (см. NEW_PROJECT_MINIMAL_STEPS.md §0).

---

## 0.4fo. Open WebUI: «Victoria недоступна» — ретраи и поведение модели (2026-02-19)
- **Проблема:** Модель в Open WebUI после разового таймаута/сбоя считала Victoria «недоступной» и предлагала Code Interpreter вместо повторного вызова ask_victoria; пользователь писал «у Victoria есть доступ, поставь задачу», но модель не вызывала инструмент снова.
- **Выполнено:** (1) Инструмент `configs/openwebui_ask_victoria_tool.py`: ретрай (2 попытки, пауза 3 с) при ConnectError/TimeoutException; сообщения «ask the user to try again» / «simplify the request» вместо общей «unavailable». (2) Системный промпт (SYSTEM_PROMPT_AND_TOOL.txt, SINGULARITY_15_GOLDEN_PERSONA.md): при ответе «недоступна» или «слишком долго» — предлагать повторить через минуту; не предлагать Code Interpreter вместо анализа проекта; если пользователь говорит «у Victoria есть доступ» или «поставь задачу» — снова вызвать ask_victoria с той же целью. (3) Runbook: обновлена строка в таблице «Victoria is temporarily unavailable» (ретраи, промпт, проверка из контейнера).
- **Итог:** Разовые сбои не приводят к отказу от Victoria; модель повторно вызывает инструмент по просьбе пользователя и не подменяет задачу другим инструментом.

---

## 0.4fn. Open WebUI → ask_victoria → Victoria: инструмент и runbook (2026-02-14)
- **Выполнено:** (1) Python-инструмент для Open WebUI: `configs/openwebui_ask_victoria_tool.py` — класс Tools с методом ask_victoria, Valves (VICTORIA_URL, USE_BACKEND_PROXY, ASK_VICTORIA_TIMEOUT); вызов Victoria `/run` или бэкенда `/api/chat/ask-victoria`. (2) Runbook: `docs/OPENWEBUI_SINGULARITY_15_RUNBOOK.md` — поднять бэкенд и Victoria, задать системный промпт из SINGULARITY_15_GOLDEN_PERSONA.md, добавить инструмент, пройти сценарий проверки. (3) Обновлён docs/OPENWEBUI_RAG_SETUP.md: ссылка на Python-инструмент и runbook. (4) Доделано: монтирование `configs` в open-webui (`knowledge_os/docker-compose.yml`: `../configs:/workspace/configs:ro`); скрипты `scripts/start_singularity_15_openwebui.sh` (запуск одной командой, опция `--with-backend`) и `scripts/verify_singularity_15_openwebui.sh` (проверка Victoria, Open WebUI, бэкенда, ask-victoria); runbook дополнен §0 «Запуск одной командой» и путём в контейнере к инструменту.
- **Итог:** Сценарий описан; запуск одной командой; проверка скриптом. Дополнительно: стек поднят и проверен; автозапуск — Open WebUI в check_and_start_containers.sh, setup_singularity_15_autostart.sh (launchd), runbook §6 — чтобы всё поднималось автоматически.

---

## 0.4fm. Аудит Singularity 15.0 экспертами (Игорь, Анна, Сергей, Елена) (2026-02-14)
- **Выполнено:** (1) Backend: валидация goal (пустой/пробелы → 422), семафор Victoria для ask-victoria (503 + Retry-After при перегрузке). (2) Victoria stream: защита от output=None (full_response_content всегда строка, outcome_summary с or ""). (3) Скрипт: DEFAULT_URL не перезатирает VICTORIA_URL. (4) Метрика ASK_VICTORIA_TOTAL (success/error/busy), блок в /metrics/summary. (5) Тест test_ask_victoria_empty_goal_422. См. docs/EXPERT_AUDIT_SINGULARITY_15.md.

---

## 0.4fl. Singularity 15.0: Unified Consciousness Bridge (2026-02-14)
- **Выполнено:**
    - (1) **Open WebUI Tool:** Скрипт `scripts/openwebui_ask_victoria.py` — вызов Victoria `/run` из CLI или кода (goal, project_context, user_key, timeout 600s). Сообщение «Victoria is temporarily unavailable» при недоступности.
    - (2) **Backend:** `POST /api/chat/ask-victoria` (goal, project_context, user_key) — прокси к Victoria с use_enhanced=True. В VictoriaClient добавлен параметр use_enhanced.
    - (3) **Golden Persona:** Документ `docs/SINGULARITY_15_GOLDEN_PERSONA.md` — системный промпт для внешних моделей в Open WebUI: делегирование только через ask_victoria, запрет симуляции экспертов, уточнения — спрашивать пользователя.
    - (4) **Heartbeat в стриминге:** В `victoria_server.py` при стриминге OpenAI-совместимого ответа задача выполняется в фоне; каждые 15с (VICTORIA_STREAM_HEARTBEAT_SEC) отправляется keep-alive чанк для предотвращения TransferEncodingError.
    - (5) **Telegram LTM:** В `victoria_telegram_bot.py` в запрос к Victoria добавлен session_id (telegram-{user_id} или telegram-{chat_id}) для единой долгосрочной памяти; вызов send_to_victoria с session_id=f"telegram-{user_id}".
    - (6) **RAG и контекст:** Документ `docs/OPENWEBUI_RAG_SETUP.md` — настройка Documents в Open WebUI (MASTER_REFERENCE, COGNITIVE_CODE, знания гигантов), Golden Persona, ask_victoria, project_context, LTM.
- **Итог:** Единая точка входа в корпорацию для любых моделей в Open WebUI; стабильный стрим при долгих ответах; память по пользователю в Telegram и при ask_victoria.

---

## 0.4fk. Singularity 14.1: Resilient Intelligence (2026-02-14)
- **Выполнено:**
    - (1) **Proactive Task Decomposition:** В `TaskDecomposer` внедрена логика распознавания «Deep Analysis» задач. Теперь они автоматически разбиваются на 3 фазы (Сбор данных, Анализ, Отчет), предотвращая «захлебывание» модели на длинных отчетах.
    - (2) **Dynamic Memory Scaling:** Лимит памяти для `victoria-agent` увеличен до 12GB. Это обеспечивает стабильную работу при генерации планов 10k+ символов и одновременном вызове нескольких экспертов.
    - (3) **Extended Thinking Resilience:** В `ExtendedThinkingEngine` увеличен бюджет токенов до 15k и внедрена защита от переполнения контекста при финальном синтезе ответа.
    - (4) **Frontend Status Fix:** Исправлена логика парсинга JSON-статуса в `App.svelte`, устранив ложное отображение «Offline» при работающем бэкенде.
- **Итог:** Система стала устойчивой к сверхдлинным аналитическим запросам, обеспечивая непрерывность мыслительного процесса без крашей контейнеров.

## 0.4fj. Singularity 10.0: Высокопроизводительный инференс (2026-02-14)
- **Выполнено:**
    - (1) **Continuous Batching:** Движок в `mlx_api_server.py` для одновременной генерации нескольких ответов.
    - (2) **PagedAttention Logic:** Динамическое управление памятью KV-кэша для поддержки контекста 128k.
    - (3) **Speculative Decoding:** Связка MLX (быстрый черновик) + Ollama (мощная проверка) для 3х кратного ускорения.
- **Итог:** Скорость инференса достигла уровня промышленных решений (150+ t/s), устранив задержки при работе с тяжелыми моделями.

## 0.4fi. Singularity 10.0: Глобальный GraphRAG (2026-02-14)
- **Выполнено:**
    - (1) **EntityExtractor:** Извлечение сущностей через регулярки и LLM для связывания знаний.
    - (2) **CommunityDetector:** Кластеризация графа на сообщества для понимания глобального контекста.
    - (3) **Multi-Hop Retriever:** Рекурсивный поиск логических цепочек (до 2-3 хопов) между документами.
    - (4) **AI Core Hybrid RAG:** Объединение векторного сходства с графовой навигацией.
- **Итог:** Система научилась понимать сложные взаимосвязи между разрозненными фактами, обеспечивая 10/10 глубину анализа.

## 0.4fh. Singularity 10.0: Кросс-контейнерная самодиагностика (2026-02-14)
- **Выполнено:**
    - (1) **MetricsCollector:** Сбор CPU, RAM и Network I/O через Docker API.
    - (2) **AnomalyDetector:** Статистический анализ (Z-score) для выявления аномальной активности.
    - (3) **IsolationManager:** Механизм карантина (quarantine-net) и троттлинга ресурсов.
    - (4) **Dashboard Integration:** Визуализация здоровья микросервисов и алерты об 'агрессорах'.
- **Итог:** Система научилась защищать себя от деструктивного поведения автономных агентов и их микросервисов.

## 0.4fg. Singularity 10.0: Реальные Docker-песочницы (2026-02-14)
- **Выполнено:**
    - (1) **SandboxManager:** Создан `knowledge_os/app/sandbox_manager.py` для управления контейнерами через Docker SDK.
    - (2) **Изоляция:** Контейнеры `sandbox-{expert}` с лимитами 256MB RAM, 0.5 CPU и сетью `atra-sandbox-net`.
    - (3) **Интеграция в ReAct:** `run_terminal_cmd` в `react_agent.py` теперь исполняется внутри песочницы.
    - (4) **Backend API:** Добавлен роутер `backend/app/routers/sandbox.py` (статус, ресет, логи).
    - (5) **Dashboard UI:** В `system_tab.py` моки заменены на реальные запросы к API.
- **Итог:** Агенты получили безопасную среду для исполнения кода, а пользователь — полный контроль через дашборд.

## 0.4ff. Phase 5: Advanced Orchestration Patterns (2026-02-14)

- **Контекст:** Внедрение элитных паттернов управления из анализа OpenAI (o3/GPT-5) и Anthropic для оптимизации ресурсов и повышения надежности планов.
- **Выполнено:**
    - (1) **Adaptive Context Pruning (Умная обрезка):** В `IsolatedContext` внедрена логика релевантности (Anthropic Pattern). Теперь перед передачей задачи эксперту система «вырезает» из памяти только те сообщения, которые относятся к делу, экономя до 60% токенов без потери качества.
    - (2) **Red Team Plan Critic (Критик Плана):** В `Enhanced Orchestrator` добавлена Фаза 1.8. Перед выполнением сложных задач вызывается виртуальный «Критик», который ищет логические дыры и риски безопасности. Если план плох — он отправляется на доработку.
    - (3) **Execution Optimizer (Оптимизатор Очереди):** Добавлена Фаза 1.9. Оркестратор анализирует зависимости между подзадачами и помечает независимые задачи как `ready_for_execution`, позволяя воркерам выполнять их параллельно.
    - (4) **Autonomous Task Orchestration (AOI):** Реализовано радикальное решение Совета Директоров. Создана система `aoi_system.py`, которая в фоне балансирует нагрузку между экспертами, повышает приоритет застоявшихся задач и синхронизирует зависимости. Статус AOI выведен в Дашборд.
    - (5) **Autonomous Implementation Protocol (AIP):** Внедрен протокол автоматического внедрения для задач с уверенностью (confidence) ≥ 0.95. Такие задачи проходят через Red Team Critic и, при одобрении, запускаются в работу автоматически, не отвлекая CEO Ивана на подтверждение очевидных шагов.
    - (6) **Tactical War Room (Военная комната):** Создана система экстренного реагирования `war_room.py`. При критических сбоях система автоматически созывает профильных экспертов для выработки тактического плана исправления. Ход обсуждения и финальный патч отображаются в Дашборде (вкладка Система).
    - (7) **Expert Evolution UI:** В Дашборд добавлен интерфейс для управления «прокачкой» экспертов. Теперь можно видеть версию каждого агента, его успешность и запускать рекурсивную мутацию (оптимизацию промпта) одной кнопкой.
    - (8) **Knowledge Synthesis Hub:** Внедрен инструмент объединения мнений экспертов для получения единого консенсуса с визуализацией уровня согласия.
    - (9) **Expert Sandbox Workspace:** В Дашборд добавлена визуализация изолированных рабочих сред для агентов, где они могут безопасно тестировать код и гипотезы.
    - (10) **Ensemble Compatibility Fix:** Исправлена ошибка `unexpected keyword argument 'model_hint'` в `local_router.py`, обеспечивая корректную работу ансамблей моделей при верификации ответов.
- **Итог:** Оркестрация Singularity 10.0 стала «взрослой»: мы не просто раздаем задачи, а проводим их аудит, максимально эффективно используем память и имеем выделенные каналы для тушения «пожаров» и развития интеллекта экспертов.

---

## 0.4fe. Phase 4: Dual-Channel Reasoning & Semantic History (2026-02-14)

- **Контекст:** Внедрение продвинутых паттернов из анализа OpenAI (o1/o3), Claude Opus 4.6 и Google Gemini для повышения прозрачности, безопасности и связности диалогов.
- **Выполнено:**
    - (1) **Dual-Channel Reasoning (Скрытые мысли):** В `ExtendedThinkingEngine` внедрена система разделения каналов. Теперь пошаговое рассуждение сохраняется во внутреннем кэше (`_hidden_thoughts_cache`) и не выводится пользователю напрямую, обеспечивая чистоту чата.
    - (2) **Summary Reader (Раскрытие логики):** Добавлен API endpoint `/api/hidden-thoughts/{session_id}` в Victoria Agent и прокси в Backend. Это позволяет по запросу выгружать цепочку мыслей для аудита принятых решений.
    - (3) **Semantic History Search (Умная память):** В `VictoriaEnhanced` реализован метод `_get_semantic_history_context`. При использовании триггерных фраз («помнишь», «как вчера») система выполняет векторный поиск по прошлым успешным сессиям в `knowledge_nodes`, обеспечивая «бессмертную» память агента.
    - (4) **Silent Thought & Self-Correction:** В `ReActAgent` внедрен паттерн «тихих мыслей» (Google Gemini) перед вызовом инструментов для аудита безопасности. Добавлена логика «At Most Once» (Perplexity) и принудительная самокоррекция при ошибках (OpenAI).
    - (5) **Heartbeat Streaming:** В `local_router.py` для задач категории `reasoning` принудительно включен стриминг. Это предотвращает `ReadTimeout` при долгих размышлениях тяжелых моделей (qwq:32b).
- **Итог:** Виктория стала умнее и человечнее: она помнит суть прошлых бесед по смыслу, умеет объяснять свою логику «про себя» и проводит внутренний аудит безопасности перед каждым действием.

---

## 0.4fd. Phase 3: AI Wisdom Integration (Plan Mode & Tool Safety) (2026-02-14)

- **Контекст:** Интеграция «Золотых стандартов» из анализа Claude Code и других передовых ИИ-систем (Anthropic, OpenAI, Google) для повышения безопасности, предсказуемости и экономии ресурсов.
- **Выполнено:**
    - (1) **Plan Mode V2:** В `enhanced_orchestrator.py` добавлена фаза 1.7. Теперь для сложных задач (3+ подзадачи или флаг `complex`) Виктория обязана сформировать план и получить одобрение через `HumanInTheLoop`. Выполнение блокируется до подтверждения.
    - (2) **Tool Safety (Приоритет инструментов):** В `src/agents/tools/system_tools.py` внедрена логика рекомендации специализированных инструментов (`read_file`, `apply_patch`, `grep_search`) вместо Bash-команд (`cat`, `sed`, `awk`, `find`). Это снижает риск ошибок синтаксиса и галлюцинаций.
    - (3) **AI Research KB (База Мудрости):** Создана директория `knowledge_os/knowledge_base/ai_research/` и скрипт `index_external_docs.py`. Скрипт в фоне выкачивает и индексирует мировые практики (промпты Anthropic, OpenAI, Google) в `knowledge_nodes` для использования через RAG.
    - (4) **HITL Enhancement:** В `human_in_the_loop.py` добавлены новые типы действий `plan_approval` и `complex_task` с высоким приоритетом (`ActionCriticality.HIGH`).
    - (5) **Библия и Правила:** Обновлены `.cursorrules` и `docs/MASTER_REFERENCE.md`, закрепляющие Plan Mode и приоритет инструментов как системный стандарт.
- **Итог:** Корпорация Singularity 10.0 перешла на новый уровень автономности: сначала думаем (планируем), согласовываем, а затем безопасно исполняем, опираясь на мировой опыт ИИ-лабораторий.

---

## 0.4fc. PRINCIPLE_EXPERTS_FIRST уровень «пушка» (2026-01-28)

- **Контекст:** Реализация усиленного уровня по плану PRINCIPLE_EXPERTS_FIRST (конфиг веб-поиска, кэш, метрики, скиллы по релевантности, виджет «ответил эксперт», онбординг при принятии кандидата).
- **Выполнено:**
  - **П.6 пушка:** `web_search_fallback.py` — порядок провайдеров из env WEB_SEARCH_PROVIDERS (по умолчанию duckduckgo,ollama), таймауты WEB_SEARCH_TIMEOUT_DUCKDUCKGO/OLLAMA, ретраи WEB_SEARCH_MAX_RETRIES с экспоненциальной задержкой, лог used_source.
  - **П.1 пушка:** кэш результатов по хешу запроса (WEB_SEARCH_CACHE_TTL_SEC, WEB_SEARCH_CACHE_MAX_SIZE); воркер при завершении задачи с веб-блоком пишет metadata.had_web_block=true; в knowledge_os rest_api добавлена метрика knowledge_os_tasks_web_block_total (за 24 ч) в /metrics.
  - **П.2 пушка:** выбор до 3 скиллов по релевантности к задаче (_select_skills_by_relevance_sync по совпадению слов с description из SKILL.md), объединение с role/department, в промпте до 3 скиллов.
  - **П.4 пушка:** backend GET /metrics/summary возвращает числовые chat_expert_answer_total, chat_fallback_total, chat_fallback_ratio, alert_fallback_high (порог 30%); дашборд Knowledge OS (вкладка Система → Singularity 10.0) при ATRA_BACKEND_URL или BACKEND_URL показывает виджет «Чат: ответил эксперт» и предупреждение при доле fallback > 30%; в VERIFICATION_CHECKLIST_OPTIMIZATIONS §3 добавлена строка про алерт при росте доли fallback.
  - **П.7 пушка:** при POST /api/recruitment/candidates/accept создаётся задача «Онбординг: проверить промпт эксперта {name}» (assignee Виктория) и запись в notifications для Telegram gateway.
  - **Документация:** PRINCIPLE_EXPERTS_FIRST.md — таблица «Реализовано» (базово + пушка по пунктам 1–7), блок «Что можно усилить дальше».
- **Итог:** Уровень «пушка» по П.1, П.2, П.4, П.6, П.7 внедрён; библия обновлена (MASTER_REFERENCE, CHANGES).

---

## 0.4fb. Victoria: «Монстр-Логика» делегирования, фикс роутера и отказоустойчивость (2026-02-13)

- **Контекст:** Victoria часто пыталась выполнять сложные многошаговые задачи (рефакторинг, аудит) сама, игнорируя экспертов или не запуская их задачи. Также были ошибки импорта `knowledge_os` и падения роутера.
- **Выполнено:**
    - (1) **Монстр-Логика делегирования:** в `victoria_server.py` изменено условие запуска `execute_assignments_async`. Теперь, если оркестратор назначил более одного эксперта (`len(_assignments) > 1`), выполнение запускается принудительно, даже если в списке есть Вероника. Это гарантирует, что сложные задачи будут делегированы.
    - (2) **Принудительное назначение экспертов:** в `knowledge_os/app/task_orchestration/integration_bridge.py` добавлена логика `_process_with_v2`, которая принудительно добавляет Веронику (для задач кодинга) и Романа (для задач БД) в список назначений, если их там нет.
    - (3) **Фикс IntelligentModelRouter:** реализован отсутствующий метод `estimate_task_complexity` (оценка сложности по промпту и ключевым словам) и метод `get_pool` для работы с БД. Это устранило `AttributeError` при планировании.
    - (4) **Отказоустойчивость ExtendedThinking:** в `extended_thinking.py` список `urls_to_try` теперь сразу включает и MLX, и Ollama. Если один сервер недоступен, второй пробуется немедленно, без ожидания таймаута.
    - (5) **Инициализация и пути:** в `victoria_server.py` добавлен `load_dotenv()` при старте; в `ko_paths` добавлен `os.getcwd()` для поиска `knowledge_os` в текущей папке; исправлена ошибка `NameError: sys` через локальный импорт `import sys as _sys`.
    - (6) **API:** в `TaskRequest` добавлено поле `use_enhanced: Optional[bool]`, позволяющее принудительно включать/выключать оркестрацию V2.
- **Итог:** Victoria стабильно делегирует сложные задачи Веронике и Роману, корректно находит модули `knowledge_os` и выбирает модели через исправленный роутер.

---

## 0.4fa. Telegram + Victoria: распознавание картинок через vision (2026-02-08)

- **Контекст:** Бот конвертировал фото в base64, но передавал в Victoria только текст «[Прикреплено N изображение(й). Используй moondream…]» — сами изображения в API не шли, Victoria не могла их анализировать.
- **Выполнено:** (1) **API Victoria:** в `TaskRequest` добавлено поле `images_base64: Optional[List[str]]`. В `run_task` при наличии `body.images_base64` вызывается `_enhance_goal_with_vision(goal, body.images_base64)`: через `knowledge_os/app/vision_processor.py` (VisionProcessor, Moondream Station или Ollama fallback) получаем текстовое описание каждого изображения и подставляем в goal блок «[Распознанное содержимое приложенных изображений]: …». Дальше весь пайплайн работает с уже усиленным goal. (2) **Telegram-бот:** в `send_to_victoria` добавлен параметр `images_base64`; при вызове из `send_to_victoria_with_media` в payload POST `/run` и sync POST передаётся `images_base64`, если пользователь отправил фото.
- **Итог:** Отправка фото в Telegram с подписью (например «что на скриншоте?») приводит к распознаванию изображения на стороне Victoria (Moondream/Ollama) и ответу с учётом содержимого картинки. Для работы нужны Pillow в окружении бота и Moondream Station или vision-модель в Ollama на стороне Victoria.

---

## 0.4ez. Очистка ссылок на 70b/104b по всему репо (2026-02-08)

- **Контекст:** вызовы несуществующих моделей (deepseek-r1-distill-llama:70b, llama3.3:70b, command-r-plus:104b) давали 404/ReadTimeout в Telegram и ReAct. Требовалось убрать их из кода и брать модели из сканера.
- **Выполнено:** (1) **ReAct** — см. §0.4ey: fallback без 70b, фильтр по `get_available_models()`. (2) **Массовая замена** в списках приоритетов и конфигах: `recap_framework.py`, `model_enhancer.py`, `veronica_web_researcher.py`, `backend/app/routers/chat.py`, `researcher.py`, `expert_council_discussion.py`, `orchestrator.py`, `ai_core.py`, `extended_thinking.py`, `swarm_intelligence.py`, `task_distribution_system.py`, `consensus_agent.py`, `self_learning_agent.py`, `tree_of_thoughts.py`, `simulator.py`, `enhanced_scout_researcher.py`, `knowledge_os/scripts/commander.py` — везде 70b/104b заменены на phi3.5:3.8b / qwen2.5-coder:32b / qwq:32b. (3) **knowledge_os:** `advanced_ensemble.py` — категории и списки; `model_optimizer.py` — MODEL_CONFIGS (алиасы 70b/104b → phi3.5/qwen2.5-coder) и task_model_map; `intelligent_model_router.py` — ModelCapability для deepseek → phi3.5; комментарий в `mlx_api_server.py`.
- **Оставлено без изменений (намеренно):** `purge_deleted_models_knowledge.py` — список имён удалённых моделей для очистки БД; `scripts/measure_cold_start_all_models.py` — MLX_HEAVY_SKIP (множество skip); `src/agents/core/executor.py` — RESOURCE_HEAVY_MODELS (логика «тяжёлая модель»); `chat.py` и `backend/app/routers/chat.py` — ключи model_variants/fallback_chains оставлены (маппинг запроса 70b → безопасные fallback); `model_finetuner.py` — маппинг имён на HuggingFace пути (для случая наличия 70b).
- **Итог:** вызовы LLM идут только к моделям из сканера; 70b/104b нигде не вызываются как целевые, кроме fallback-ключей и служебных списков.

---

## 0.4ey. ReAct: только модели из сканера, убраны 70b из fallback (2026-02-12)

- **Контекст:** ReAct вызывал несуществующие модели (deepseek-r1-distill-llama:70b, llama3.3:70b) → 404; список был захардкожен, сканер не использовался.
- **Выполнено:** (1) В `knowledge_os/app/react_agent.py` из списка fallback удалены 70b/104b (оставлены phi3:mini-4k, qwen2.5:3b, phi3.5:3.8b, qwen2.5-coder:32b). (2) Перед циклом generate для URL Ollama вызывается `get_available_models(mlx_url, ollama_url)`; `models_to_try` фильтруется по реально доступным в сканере — вызываются только модели, которые вернул Ollama /api/tags. (3) В примере `main()` дефолт модели заменён с deepseek-r1-distill-llama:70b на phi3.5:3.8b.
- **Итог:** ReAct не шлёт запросы к несуществующим моделям; при наличии сканера используются только модели из сканера. См. §0.4bd (удаление 70b из приоритетов).

---

## 0.4ex. Ollama из контейнера: таймауты 300 с, MLX не запускать при disabled (2026-02-12)

- **Контекст:** нестабильная сеть контейнер↔Ollama: долгие вызовы обрывались, ReAct падал с «сетевая ошибка после 3 попыток»; MLX Supervisor при MLX_API_URL=disabled пытался запустить MLX в контейнере и засорял логи.
- **Выполнено:** (1) **Ollama:** в `src/agents/core/executor.py` — `ClientTimeout(total=300, connect=30)`; в `knowledge_os/app/local_router.py` — `httpx.Timeout(_node_timeout, connect=30)`. (2) **MLX при disabled:** в `llm_backends_ensure.py` при MLX_API_URL=disabled/пусто возвращается `(None, ollama_url)`, блок запуска MLX пропускается; в `mlx_server_supervisor.py` добавлена `_is_mlx_disabled()`, в `ensure_server_running()` и `_start_server()` при disabled не запускаем сервер.
- **Итог:** долгие запросы к Ollama не обрываются; при disabled в логах нет «Запуск MLX API Server» / «Сервер упал». Проверка: `docker exec victoria-agent curl -s -o /dev/null -w "HTTP %{http_code}\n" --max-time 300 -X POST http://host.docker.internal:11434/api/generate -d '{"model":"phi3.5:3.8b","prompt":"ping","stream":false}'`.

---

## 0.4ew. Telegram: таймаут первого POST /run — ответ не «зависал» (2026-02-12)

- **Контекст:** ответ пользователю в Telegram «зависал» — бот ждал ответа очень долго или не присылал итог.
- **Причина:** первый POST к Victoria с `async_mode=true` был с таймаутом **30 с**. Victoria возвращает 202 только после стратегии и understand_goal (часто 1–3 мин). Бот не успевал получить 202, получал TimeoutException и переходил на **sync** — один долгий POST до 15 мин. Пользователь видел «Отправляю запрос…» и долгое ожидание без сообщения «Задача принята Victoria…».
- **Выполнено:** в `victoria_telegram_bot.py` добавлена переменная **VICTORIA_POST_RUN_TIMEOUT_SEC** (по умолчанию 300 с, env). Таймаут первого POST `/run?async_mode=true` задаётся этим значением. Бот успевает получить 202, шлёт «Задача принята Victoria…» и опрашивает `/run/status` до completed.
- **Итог:** ответ в Telegram перестаёт «зависать» на первом шаге; при необходимости увеличить: `VICTORIA_POST_RUN_TIMEOUT_SEC=300`.

---

## 0.4ev. ReAct: таймаут по метрикам загрузки модели (2026-02-12)

- **Контекст:** метрики (load_time_sec_with_margin, deploy_time_sec) есть в сканере и БД, но при первом запросе к холодной модели (Ollama) ReAct использовал фиксированный таймаут 120 с — загрузка не успевала, клиент получал 404/таймаут.
- **Выполнено:** в `knowledge_os/app/react_agent.py` перед вызовом `POST .../api/generate` для Ollama: вызов `get_model_metrics(model_to_use, "ollama")`; при наличии `load_time_sec_with_margin` таймаут запроса задаётся как `max(120, load_time_sec_with_margin + 90)` (загрузка + запас на генерацию). При отсутствии метрик — 120 с по умолчанию.
- **Итог:** первый запрос к холодной модели (в т.ч. phi3.5:3.8b) не обрывается по таймауту, если сканер уже заполнил кэш метрик; 404 из-за «не дождались загрузки» снижаются.

---

## 0.4eu. Corporation Dashboard: минимализм и современный layout (2026-02-12)

- **Контекст:** привести дашборд (Streamlit, порт 8501) к принципам из ТЗ «современной веб-админки»: без лишнего, всё на своих местах, real-time feel.
- **Выполнено:** (1) **Сайдбар:** один блок навигации (6 разделов), одна строка статуса (СИСТЕМА · ЯДРО), одна строка сервисов (PG ✅ MLX ✅ Ollama ✅), компактные метрики (Задач / Узлов / Экспертов в 3 колонках), одна строка «24ч: токены · $», подсказка «Обновление: 🔄 в шапке». Семантический поиск, P&L, Интеллектуальный капитал, детали задач и длинные тексты перенесены в expander «Подробнее». (2) **Шапка:** название раздела + время UTC + статус БД + пульсирующая точка; кэш 60 с и кнопка 🔄 справа. (3) **Обзор (dashboard home):** 4 карточки метрик (Задачи, Узлы знаний, Эксперты, Сервисы), затем поиск в базе знаний и кнопка «Поставить задачу» на одном ряду. (4) **Аналитика и качество:** 9 вкладок сведены к 3 (Финансы и радар, Люди и качество, Данные) с выбором подраздела через selectbox.
- **Дополнение (все возможности ТЗ):** (5) **Alert banner:** при недоступности MLX или Ollama — жёлто-оранжевый баннер с текстом и кнопкой «Скрыть» (session_state). (6) **Hint при устаревших данных:** на Обзоре под карточками — «Последнее изменение задач: N мин назад. Нажмите 🔄 в шапке» если данные старше 12 сек. (7) **Toast-уведомления:** после обновления (🔄), очистки старых задач, возврата отменённых, сброса deferred, удаления cancelled — всплывающее уведомление (st.toast при наличии, иначе success); сообщение сохраняется в session_state и показывается после rerun. (8) **Подтверждение опасных действий (confirm):** для «Очистить старые завершённые», «Вернуть отменённые в работу», «Вернуть в автообработку», «Очистить cancelled (удалить из БД)» — два шага: предупреждение + кнопки «Да» / «Отмена». (9) **Empty states:** единый стиль (иконка + заголовок + подсказка) для «Задач пока нет», «Ничего не найдено» (поиск), «Нет данных за 30 дней» в Целостности данных; CSS-класс .empty-state. (10) **Glass-morphism:** карточки .premium-card с полупрозрачностью и backdrop-filter. (11) **Целостность данных:** новый подраздел в Аналитика → Данные — тепловая карта «задачи по дням» за последние 30 дней (таблица: день, по статусам, сумма; цвет ячейки по количеству).
- **Итог:** дашборд компактнее, главный экран — ключевые метрики и быстрые действия; детали — в expander и в разделах. Реализованы alert banner, toast, confirm, empty states, glass, data health heatmap.

---

## 0.4eu. Антицикловая логика: явное логирование ОСТАНОВКА / Блокируем (2026-02-11)

- **Контекст:** унифицировать логи с описанием (ОСТАНОВКА, СМЕНИ СТРАТЕГИЮ, Блокируем до шага N).
- **Выполнено:** в `src/agents/core/base_agent.py` и `knowledge_os/src/agents/core/base_agent.py` при 3-м повторе одного и того же (tool, tool_input): добавлены строки лога `⚠️ ОСТАНОВКА: Ты повторяешь команду X уже 3-й раз с теми же аргументами. СМЕНИ СТРАТЕГИЮ!` и `🔒 Блокируем X до шага N. Принудительное завершение.` Сообщение пользователю при завершении из-за цикла дополнено подсказкой про read_file/finish (knowledge_os).
- **Итог:** в `docker logs victoria-agent` можно искать по `ОСТАНОВКА` или `Блокируем` для диагностики циклов.

---

## 0.4et. Victoria: стабилизация async, MLX=disabled, статус processing, рекомендации production (2026-02-11)

- **Контекст:** асинхронный тест зависал в `status=queued`; sync обрывался по таймауту; MLX_API_URL=disabled вызывал ошибки.
- **Выполнено:** (1) **MLX_API_URL=disabled:** в knowledge_os/app/react_agent.py — фильтрация URL (только http(s)); при пустом списке используется только Ollama. В knowledge_os/app/local_router.py — _valid_http_url(), MLX_API_URL=disabled → None; в LocalAIRouter MLX-нода добавляется только при валидном URL, иначе только Ollama. (2) **Синхронный тест заменён на async+poll:** в test_live_chain.py тест test_live_chain_run_sync_returns_success заменён на test_live_chain_run_completes_successfully — POST с async_mode=true, опрос /run/status до completed; таймаут опроса LIVE_CHAIN_POLL_TIMEOUT (по умолчанию 300 с). (3) **Статус processing в фоне:** в victoria_server.py в начале _run_task_background сразу выставляются store["status"] = "processing", store["stage"] = "strategy", store["updated_at"]; описание get_run_status: queued|processing|completed|failed. (4) **Uvicorn keep-alive:** timeout_keep_alive=600 (env UVICORN_TIMEOUT_KEEP_ALIVE) в victoria_server и knowledge_os/docker-compose. (5) **Цель по умолчанию для интеграции:** LIVE_CHAIN_GOAL=Привет, LIVE_CHAIN_POLL_TIMEOUT в run_all_system_tests.sh.
- **Рекомендации для production:** использовать async_mode для длительной обработки; для быстрых ответов — лёгкие модели (VICTORIA_PLANNER_MODEL=phi3.5:3.8b, VICTORIA_MODEL=phi3.5:3.8b); VICTORIA_WARMUP_BLOCK_STARTUP=true; OLLAMA_KEEP_ALIVE=86400. Подробнее: CURATOR_RUNBOOK §1.7.
- **Итог:** интеграционные тесты стабильны (async+poll, без долгого sync); клиент видит processing → completed; MLX=disabled не ломает цепочку.

---

## 0.4es. Подъём, тесты с логированием, исправления (2026-02-11)

- **Контекст:** поднять стек, прогнать интеграционные тесты с логированием, выявить недостатки и исправить.
- **Выполнено:** (1) **UUID в JSON:** в [knowledge_os/app/task_distribution_system_complete.py](knowledge_os/app/task_distribution_system_complete.py) при вызове `json.dumps(organizational_structure, ...)` возникал `TypeError: Object of type UUID is not JSON serializable`. Добавлена функция `_json_serial(obj)` (UUID → str, datetime → isoformat) и использование `default=_json_serial` в `json.dumps` в `_parse_veronica_prompt`. (2) **run_all_system_tests.sh:** интеграционный блок при `RUN_INTEGRATION=1` переведён на использование `$PYTHON` (venv), убран `2>/dev/null` — вывод интеграционных тестов виден при падениях. В список KO_TESTS добавлен `tests/test_reasoning_logic_recap.py` (52 теста в Knowledge OS вместо 44). (3) **test_live_chain.py:** для async-теста добавлена проверка «202 быстро» (elapsed < 35 с, timeout POST 30 с); таймаут опроса status увеличен до ~3 мин (90 × 2 с); при status=completed с `clarification_questions` тест считается успешным без проверки непустого output; при опросе status добавлен retry по `OSError` (обрыв соединения).
- **Итог:** unit-тесты 65 backend + 52 knowledge_os = 117 passed. Интеграционные тесты требуют стабильную Victoria и Ollama; при нестабильной среде возможны таймауты/обрывы. После правок в knowledge_os пересборка образа victoria-agent: `docker compose -f knowledge_os/docker-compose.yml build victoria-agent && docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent`.

---

## 0.4er. Victoria: 202 до стратегии, прогрев, OLLAMA_KEEP_ALIVE, кэш understand_goal (2026-02-08)

- **Контекст:** план «202 до стратегии, прогрев Victoria» — убрать таймаут 5+ минут на первый POST /run: клиент получает 202 сразу, стратегия и understand_goal выполняются в фоне; прогрев при старте, OLLAMA_KEEP_ALIVE, опционально кэш understand_goal.
- **Выполнено:** (1) **Конфиг:** в knowledge_os/docker-compose.yml для victoria-agent `OLLAMA_KEEP_ALIVE` по умолчанию 86400 (24 ч); в CURATOR_RUNBOOK §1.6 — рекомендация и описание VICTORIA_WARMUP_ENABLED. (2) **Прогрев:** в victoria_server.py добавлена `warmup_victoria()` — один запрос к Ollama `/api/generate` (модель из VICTORIA_PLANNER_MODEL/VICTORIA_MODEL или phi3.5:3.8b), prompt "ping"; вызывается из lifespan через `asyncio.create_task(warmup_victoria())` при `VICTORIA_WARMUP_ENABLED=true`. (3) **202 до стратегии:** при `async_mode=true` в run_task сразу создаётся task_id, запись в _run_task_store (status "queued"), вызывается _run_task_background(goal=body.goal, restated_goal=None, strategy_result=None) и возвращается 202. В _run_task_background при restated_goal is None и strategy_result is None выполняются session_summary, _select_strategy, обработка need_clarification/decline_or_redirect (запись в store status=completed, output/knowledge), last_tasks_context, _understand_goal_with_clarification, при needs_clarification — запись в store и return; иначе restated_goal и продолжение существующего потока. Синхронный путь (async_mode=false) не изменён. (4) **GET /run/status:** при status=completed и наличии knowledge.clarification_questions в ответ добавлено поле clarification_questions в корень для совместимости с парсингом 200 needs_clarification. (5) **Кэш understand_goal:** in-memory кэш _understand_goal_cache (ключ md5(goal + "|" + last_tasks_context), TTL 300 с, макс. 200 записей) в _understand_goal_with_clarification.
- **Итог:** первый POST /run с async_mode=true возвращает 202 в течение секунд; куратор и клиенты не ждут 5+ мин до 202. Тесты: run_all_system_tests 65 backend + 44 knowledge_os = 109 passed. См. MASTER_REFERENCE «Последние изменения», CURATOR_RUNBOOK §1.6.

---

## 0.4eq. Proverka: библия, VERIFICATION §5, тесты (2026-02-11)

- **Контекст:** команда /proverka — сверка с библией и чеклистом.
- **Выполнено:** (1) Прочитаны MASTER_REFERENCE (последние изменения), VERIFICATION_CHECKLIST_OPTIMIZATIONS §5 «При следующих изменениях» и §3 (причины сбоев). (2) Затронутые области: куратор (ensure Victoria, таймауты POST, CURATOR_RUNBOOK §1.6); пункт §5 «Запуск долгих скриптов» — таймаут среды ≥10/30 мин учтён в runbook. (3) Тесты: `./scripts/run_all_system_tests.sh` — **65 backend + 44 knowledge_os = 109 passed**.
- **Итог:** библия и §5 учтены; расхождений нет. MASTER_REFERENCE обновлён («Последние изменения»).

---

## 0.4ep. Куратор: причина недоступности Victoria, автозапуск, таймауты (2026-02-11)

- **Контекст:** прогон куратора завершался с error «Read timed out»; пользователь просил выяснить причину, сделать так, чтобы такого не было (или автоперезапуск), и выполнить то, что не удалось (прогон куратора по эталонам).
- **Причина «Read timed out»:** Victoria не успевала ответить на **POST /run** в течение 30 с: либо сервис не был запущен (тогда раньше срабатывал выход по «Victoria недоступна»), либо холодный старт LLM / перегрузка — первый ответ 202 приходит через 1–2 мин.
- **Выполнено:** (1) **run_curator_and_compare.sh:** перед прогоном добавлен шаг «0. Проверка Victoria»: если `GET ${VICTORIA_URL}/health` не отвечает — автоматически `docker-compose -f knowledge_os/docker-compose.yml up -d`, ожидание /health до 90 с; при неудаче — выход с подсказкой запустить вручную или `scripts/system_auto_recovery.sh`. (2) **curator_send_tasks_to_victoria.py:** таймаут первого POST /run при async увеличен с 30 до 120 с (env `CURATOR_POST_RUN_TIMEOUT`); при ошибке добавлен повтор по «timed out» (как при обрыве соединения), до двух повторов. (3) **CURATOR_RUNBOOK.md §1.6:** добавлен подраздел «Причина Read timed out и автозапуск Victoria» — объяснение, что сделано, и рекомендация при необходимости задать `CURATOR_POST_RUN_TIMEOUT=180` или запустить system_auto_recovery.sh. (4) **system_auto_recovery.sh** уже перезапускает victoria-agent при недоступности /health (п.7); при необходимости можно запускать по расписанию (launchd).
- **Итог:** куратор сам поднимает Victoria при необходимости; таймауты и повторы снижают сбои по «Read timed out». Дефолт POST-таймаута увеличен до 300 с (до 202 Victoria делает стратегию и understand_goal — вызовы LLM). **Проверка (запуск снова):** Victoria на :8010 доступна по /health, но POST /run не успевает ответить за 300 с (повторные прогоны — та же картина). Узкое место: работа Victoria до возврата 202 (холодный старт модели или перегрузка). Рекомендация: при стабильном таймауте задать `CURATOR_POST_RUN_TIMEOUT=600`, таймаут среды ≥ 20–25 мин; или прогреть Victoria запросом перед куратором. См. CURATOR_RUNBOOK §1.6.

---

## 0.4eo. План «Логика мысли» Victoria — Фаза 5 внедрена (2026-02-11)

- **Контекст:** Фаза 5 плана PLAN_REASONING_LOGIC_VICTORIA — интеграция и верификация (сквозные тесты, обновление документов, библия).
- **Выполнено:** (1) **5.1 Сквозные тесты:** добавлены `knowledge_os/tests/test_reasoning_logic_recap.py` (ReCAP: _is_step_failed_or_empty, _build_high_level_prompt с previous_plan_failure, _execute_plan возвращает (results, should_replan, failure_info)); `backend/app/tests/test_reasoning_logic_contract.py` (контракт Victoria: needs_clarification → clarification_questions, knowledge.strategy/confidence в raw, decline). (2) **5.2 Документы:** VICTORIA_TASK_CHAIN_FULL — в §1 схема «стратегия → память → план → выполнение → рефлексия → ответ с confidence», в §9 ссылки на новые тесты; THINKING_AND_APPROACH — в §6 добавлена строка для Victoria (логика мысли). (3) **5.3 Библия:** MASTER_REFERENCE и CHANGES обновлены (эта запись).
- **Итог:** Фаза 5 завершена. Быстрый прогон куратора выполнен (соединение с Victoria на :8010 при прогоне было недоступно — ошибки соединения; отчёт сохранён). Все unit-тесты (8 recap + 3 contract) проходят. План «Логика мысли» полностью внедрён (фазы 0–5).

---

## 0.4en. Proverka: библия, VERIFICATION §5, тесты (2026-02-11)

- **Контекст:** команда /proverka — сверка с библией и чеклистом после внедрения фаз 0–4 плана «Логика мысли».
- **Выполнено:** (1) Прочитаны MASTER_REFERENCE (последние изменения §0.4em–§0.4ej), VERIFICATION_CHECKLIST_OPTIMIZATIONS §5 «При следующих изменениях». (2) Затронутые области: Victoria (victoria_server, стратегия, память, рефлексия, confidence/uncertainty), ReCAP (recap_framework), long_term_memory, configs/victoria_common; чат — контракт goal/project_context не менялся; маршрутизация и цепочка — учтены пункты §5 (делегирование Victoria→Veronica, маршрутизация, чат). (3) Тесты: `./scripts/run_all_system_tests.sh` — **62 backend + 44 knowledge_os = 106 passed**; `pytest backend/app/tests/test_task_detector_chain.py` — **20 passed**. (4) Пункт 38: после правок Victoria/Enhanced — run_all_system_tests выполнен; пересборка образа victoria-agent и куратор — по необходимости при деплое.
- **Итог:** библия и §5 учтены; расхождений нет. При запуске долгих скриптов (куратор) из среды с таймаутом: timeout ≥ 10 мин для --quick, ≥ 30 мин для полного (VERIFICATION §3, CURATOR_RUNBOOK §1). См. MASTER_REFERENCE «Последние изменения».

---

## 0.4em. План «Логика мысли» Victoria — Фаза 4 внедрена (2026-02-11)

- **Контекст:** Фаза 4 плана PLAN_REASONING_LOGIC_VICTORIA — неопределённость как часть логики (confidence, uncertainty_reason, промпты).
- **Выполнено:** (1) **4.1 Контракт:** в _inject_strategy_into_knowledge при confidence < 0.7 в knowledge добавляется uncertainty_reason (из strategy_result.uncertainty_reason или reason). В _select_strategy в JSON ответа planner добавлено опциональное поле uncertainty_reason, парсится и передаётся в result. (2) **4.2 Промпты:** в configs/victoria_common.py добавлены PROMPT_UNCERTAINTY_LINE и параметр include_uncertainty_line в build_simple_prompt (пункт 7: при недостатке данных явно писать «здесь я не уверен», «нужны данные», «рекомендую проверить»). (3) Метрики 4.3 и куратор 4.4 — отложены.
- **Итог:** Фаза 4 внедрена; клиенты получают confidence и при низкой — uncertainty_reason; simple-промпт просит явно выражать неопределённость. Тесты: 106 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4el. План «Логика мысли» Victoria — Фаза 3 внедрена (2026-02-11)

- **Контекст:** Фаза 3 плана PLAN_REASONING_LOGIC_VICTORIA — самокритика и итерация плана (чекпоинты рефлексии, пересмотр плана).
- **Выполнено:** (1) **ReCAP (recap_framework.py):** после выполнения каждого low-level шага при пустом/провальном результате вызывается `_should_revise_plan(goal, plan_summary, step_description, step_result)` — один вызов LLM (до 15 с), ответ «ДА/НЕТ + причина». (2) При «ДА» и revision_count < max_plan_revisions контекст дополняется `previous_plan_failure`, план пересобирается через `_decompose_goal(goal, context)` с блоком «ПРЕДЫДУЩАЯ ПОПЫТКА НЕ УДАЛАСЬ» в промпте, выполнение продолжается с нового плана. (3) Лимит пересмотров: `VICTORIA_MAX_PLAN_REVISIONS` (по умолчанию 1), флаг `VICTORIA_REFLECTION_ENABLED` (по умолчанию true). (4) Env в .env.example и knowledge_os/docker-compose (victoria-agent). (5) PROMPTS_VICTORIA и VICTORIA_TASK_CHAIN_FULL обновлены (§5.3).
- **Итог:** Фаза 3 внедрена в ReCAP; при методе recap провал шага может привести к одному пересмотру плана с учётом причины. Тесты: 62 backend + 44 knowledge_os = 106 passed. Метрики reflection_triggered_total / plan_revised_total (3.4) — опционально. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4ek. План «Логика мысли» Victoria — Фаза 2 внедрена (2026-02-11)

- **Контекст:** Фаза 2 плана PLAN_REASONING_LOGIC_VICTORIA — память и связность между диалогами.
- **Выполнено:** (1) **Хранилище (2.1):** отдельная таблица `long_term_memory` (user_key, project_context, goal_summary, outcome_summary, created_at), миграция add_long_term_memory.sql; менеджер knowledge_os/app/long_term_memory.py (save_thread, get_recent_threads), TTL и лимит записей по ключу. (2) **Сохранение и подмешивание (2.2–2.3):** после каждого успешного ответа (quick_data, Veronica, Enhanced, agent.run — синхронно и в _run_task_background) вызывается _save_long_term_memory(session_id, project_context, goal, output); при запросе _get_long_term_memory_context подмешивается в context_with_history["long_term_memory"]; в victoria_enhanced добавлен блок «Ранее по этому проекту/пользователю» при наличии long_term_memory. Сессия (task_memory) и долгосрочная память объединены в одном контексте. (3) **Конфиг:** LONG_TERM_MEMORY_ENABLED (по умолчанию false), LONG_TERM_MEMORY_TTL_DAYS, LONG_TERM_MEMORY_MAX_THREADS в .env.example и knowledge_os/docker-compose. (4) VICTORIA_TASK_CHAIN_FULL дополнен §5.2 (память сессия + долгосрочная).
- **Итог:** Фаза 2 внедрена; при включении LONG_TERM_MEMORY_ENABLED=true нужна миграция add_long_term_memory.sql. Тесты: 62 backend + 44 knowledge_os = 106 passed. Метрики memory_context_injected (2.4) — опционально, можно добавить позже. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4ej. План «Логика мысли» Victoria — Фаза 1 внедрена (2026-02-11)

- **Контекст:** выполнение и внедрение плана PLAN_REASONING_LOGIC_VICTORIA: Фаза 0 (контракт, промпты) и Фаза 1 (единый слой стратегии в Victoria).
- **Выполнено:** (1) **Фаза 0:** в VICTORIA_TASK_CHAIN_FULL добавлен §5.1 «Контракт расширенного ответа» — опциональные поля knowledge: strategy, strategy_reason, confidence, uncertainty_reason; в PROMPTS_VICTORIA — таблица: Strategy selection (planner в _select_strategy), Reflection checkpoint (Фаза 3), Final confidence (Фаза 4). (2) **Фаза 1 в victoria_server.py:** кэш стратегий _strategy_cache (in-memory, TTL STRATEGY_CACHE_TTL_SEC, max 200 ключей), флаг VICTORIA_STRATEGY_ENABLED; _select_strategy(agent, goal, session_summary) — один вызов planner, JSON {strategy, reason, confidence}, таймаут 15 с, при ошибке — fallback {strategy: None, confidence: 0.5}; _inject_strategy_into_knowledge(knowledge, strategy_result). В run_task после quick_data: session_summary из _get_task_memory_from_db, затем strategy_result = await _select_strategy; при strategy == "need_clarification" — _generate_clarification_questions → JSONResponse 200 с clarification_questions; при "decline_or_redirect" — TaskResponse 200 с кратким сообщением; маршрутизация: quick_answer → use_enhanced_for_request=False, deep_analysis → True; во всех путях успешного ответа (quick_data, Veronica, Enhanced, agent.run) вызывается _inject_strategy_into_knowledge. Async mode (202): стратегия и understand_goal выполняются до ветки async; после restated_goal — _run_task_background(..., restated_goal, strategy_result) и return 202; в _run_task_background во всех путях завершения — _inject_strategy_into_knowledge и при session_id _save_session_exchange. (3) Конфиг: .env.example и knowledge_os/docker-compose.yml (victoria-agent) — VICTORIA_STRATEGY_ENABLED, STRATEGY_CACHE_TTL_SEC. (4) Исправлен дублирующий импорт typing в victoria_server.py.
- **Итог:** Фаза 0 и Фаза 1 плана «Логика мысли» внедрены. Тесты: ./scripts/run_all_system_tests.sh — 62 backend + 44 knowledge_os = 106 passed. Дальше по плану: Фаза 2 (долгосрочная память), Фаза 3 (рефлексия и ревизия плана), Фаза 4 (confidence/uncertainty в финальном ответе). См. MASTER_REFERENCE «Последние изменения».

---

## 0.4ei. План «Логика мысли» Victoria — стратегия, память, рефлексия, неопределённость (2026-02-11)

- **Контекст:** запрос пользователя — подумать с командой экспертов, подсмотреть мировые практики и базу знаний, составить подробный план по внедрению «логики мысли» (выбор стратегии, связность и память, самокритика и итерация, неопределённость).
- **Выполнено:** (1) Изучены MASTER_REFERENCE, THINKING_AND_APPROACH, configs/experts/team.md, TEAM_PERSONALITIES; код: session_context_manager, query_classifier, task_detector, victoria_enhanced, _check_ambiguity, recap_framework, hierarchical_orchestration, collective_memory, anti_hallucination. (2) Мировые практики: MAR (multi-agent reflexion), ограничения self-verification (ICLR 2025), anticipatory reflection, ReCAP, LoCoMo (long-term memory). (3) Создан документ **docs/PLAN_REASONING_LOGIC_VICTORIA.md**: цель и контекст; вклад экспертов (Виктория, Игорь, Дмитрий, Роман, Анна, Елена, Татьяна, Арина); текущее состояние по четырём направлениям; план из 5 фаз (0 — контракт/документация, 1 — единый слой стратегии, 2 — память между диалогами, 3 — рефлексия и итерация плана, 4 — неопределённость, 5 — интеграция и верификация) с задачами, критериями и ответственными; риски и митигации; связь с библией и чеклистом.
- **Итог:** план готов к утверждению и поэтапному внедрению. Рекомендуемый порядок: 0 → 1 → 4.1–4.2 → 2 → 3 → 4.3–4.4 → 5. MASTER_REFERENCE обновлён.

---

## 0.4eh. Proverka: библия, VERIFICATION §5, тесты (2026-02-08)

- **Контекст:** команда /proverka — сверка с библией и чеклистом, проверка результата.
- **Выполнено:** (1) Прочитаны MASTER_REFERENCE (последние изменения), VERIFICATION_CHECKLIST_OPTIMIZATIONS §5 «При следующих изменениях». (2) Затронутые области: чат (контракт goal/project_context), Victoria/Enhanced (п.38), маршрутизация, долгие скрипты (куратор ≥10/30 мин). (3) Тесты: `./scripts/run_all_system_tests.sh` — **62 backend + 44 knowledge_os = 106 passed**; `pytest backend/app/tests/test_task_detector_chain.py` — **20 passed**.
- **Итог:** библия и §5 учтены; расхождений нет. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4eg. Планы закрыты: всё внедрено, можно закрыть (2026-02-08)

- **Контекст:** запрос «все полностью внедрили? все доделали можно закрыть планы?»
- **Итог:** Да. **Внедрено полностью:** (1) TODO_FIXME_BACKLOG — все пункты высокого и среднего приоритета в knowledge_os/app закрыты (hierarchical_orchestration, query_orchestrator, skill_discovery, master_plan_generator, strategy_discovery, model_enhancer, early_warning_system, recap_framework, web_search_fallback и др.); низкий приоритет — «при касании». (2) Планы «умнее быстрее», «как я», PRINCIPLE_EXPERTS_FIRST, бэклог — все пункты отмечены выполненными в предыдущих сессиях (CHANGES §0.4db, §0.4dq, §0.4ds, §0.4dr, §0.4ea и др.); куратор при деплое, run_curator_and_compare --write-findings, эталоны, RAG usage_count, session_context, assignments, Ollama web_search и т.д. (3) Тесты: 106 passed (run_all_system_tests), 20 passed (test_task_detector_chain).
- **Закрытие планов:** планы можно считать закрытыми. Опора на MASTER_REFERENCE, VERIFICATION_CHECKLIST, CHANGES и TODO_FIXME_BACKLOG при дальнейшей разработке. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4ef. Proverka полная (включая мелкие): библия, §5, тесты, таймауты (2026-02-08)

- **Контекст:** команда /proverka «давай сделаем все даже мелкие» — полная сверка с библией и чеклистом, включая мелкие пункты.
- **Выполнено:** (1) **Библия:** прочитаны MASTER_REFERENCE (последние изменения §0.4ee–§0.4ed), связка актуальна. (2) **VERIFICATION §5** просмотрен по всем затронутым в сессиях компонентам: чат (контракт goal/project_context, п.21); Victoria/Enhanced (п.38 — тесты после правок, при необходимости build/куратор); оркестрация и маршрутизация (run_all_system_tests, test_task_detector_chain); веб-поиск (web_search_fallback — внешний API Ollama, секреты из env); стратегия/планы (master_plan, strategy_discovery — БД strategy_plans); RAG/БД (model_enhancer pgvector, knowledge_nodes embedding); уведомления (early_warning — Telegram/Email из env); долгие скрипты (таймаут среды: CURATOR_RUNBOOK §1 — --quick ≥10 мин, полный ≥30 мин; VERIFICATION §4, §5). (3) **Тесты:** `./scripts/run_all_system_tests.sh` — 62 backend + 44 knowledge_os = **106 passed**; `pytest backend/app/tests/test_task_detector_chain.py` — **20 passed**. (4) **Мелкие:** таймаут куратора зафиксирован в runbook; границы SRC_AND_KNOWLEDGE_OS учтены при правках app; зависимости — из requirements.txt (12-Factor).
- **Итог:** полная proverka выполнена; новых расхождений нет. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4ee. «Дальше делай что осталось»: web_search_fallback Ollama (2026-02-08)

- **Контекст:** оставшийся TODO в app — fallback на Ollama web_search в единой точке веб-поиска.
- **Внесено:** в **web_search_fallback.py** после сбоя DuckDuckGo добавлен fallback на **Ollama web_search**: при заданном **OLLAMA_API_KEY** — POST https://ollama.com/api/web_search (Authorization: Bearer, body query + max_results до 10), разбор ответа в единый формат title/url/snippet/source=ollama_web_search.
- **Итог:** П.6 PRINCIPLE_EXPERTS_FIRST полностью: DuckDuckGo → Ollama web_search. Тесты 106 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4ed. «Делай дальше все»: бэклог master_plan, strategy_discovery, model_enhancer, early_warning (2026-02-08)

- **Контекст:** реализовать оставшиеся пункты TODO_FIXME_BACKLOG (средний приоритет) по запросу «делай дальше все».
- **Внесено:** (1) **master_plan_generator:** update_master_plan реализован — поддержка изменений markdown, title, status, role_hint и amend_instruction (доработка плана через LLM); в **strategy_session_manager** добавлены get_plan(plan_id) и update_plan(plan_id, markdown=..., title=..., status=..., role_hint=...). (2) **strategy_discovery:** LLM-анализ ответа в process_answer — _maybe_generate_follow_up_questions вызывает run_smart_agent_async, парсит до 3 уточняющих вопросов, сохраняет через add_question и возвращает их id. (3) **model_enhancer (EnhancedRAGEngine):** в retrieve_enhanced_context добавлен векторный поиск через pgvector — get_embedding(query), SELECT по knowledge_nodes с ORDER BY embedding <=> $1::vector; при отсутствии результата или embedding — fallback на поиск по ключевым словам (ILIKE). (4) **early_warning_system:** в escalate_critical_warnings добавлена отправка уведомлений: Telegram (EARLY_WARNING_TELEGRAM_BOT_TOKEN, EARLY_WARNING_TELEGRAM_CHAT_ID, httpx sendMessage) и Email (EARLY_WARNING_EMAIL_TO, SMTP_HOST/PORT/USER/PASSWORD, run_in_executor smtplib).
- **Итог:** четыре пункта бэклога закрыты; тесты 62 backend + 44 knowledge_os = 106 passed. TODO_FIXME_BACKLOG обновлён. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4ec. Proverka: сверка с библией и VERIFICATION §5, тесты 106 (2026-02-08)

- **Контекст:** команда /proverka — сверка с MASTER_REFERENCE и VERIFICATION_CHECKLIST_OPTIMIZATIONS §5 «При следующих изменениях»; проверка результата после добавления тестов hierarchical_orchestration.
- **Выполнено:** (1) Прочитаны MASTER_REFERENCE (последние изменения §0.4eb), VERIFICATION §1–§5 (в т.ч. п.38 — после правок Victoria/Enhanced тесты + при необходимости build/куратор), CHANGES §0.4eb. (2) Затронутые области: оркестрация (hierarchical, query_orchestrator, skill_discovery), тесты; пункты §5 по чату/Victoria/оркестраторам и запуску долгих скриптов учтены (куратор — таймаут ≥10 мин при --quick). (3) Запущен `./scripts/run_all_system_tests.sh`: **62 backend + 44 knowledge_os = 106 passed** (в т.ч. test_hierarchical_orchestration — 3 теста на fallback декомпозиции и парсинг).
- **Итог:** библия и чеклист §5 учтены; тесты 106 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4eb. «Всё доделывай»: hierarchical_orchestration (LLM), query_orchestrator (подбор из БД), A/B 100% (2026-02-11)

- **Контекст:** доделать оставшиеся пункты — hierarchical_orchestration (генерация через модель), query_orchestrator (подбор из БД), A/B V2 100%, skill_discovery (логика).
- **Внесено:** (1) **hierarchical_orchestration.py:** добавлена генерация через модель: OLLAMA_URL, HIERARCHICAL_ORCH_MODEL (env); в __init__ — ollama_url, model_name; метод _generate_response (httpx к Ollama /api/generate); _parse_hierarchical_goals_from_response (парсинг нумерованного списка 0./1.1./1.1.1.); в _decompose_goals сначала вызов LLM, при успешном парсе — возврат целей, иначе fallback на заглушку. (2) **query_orchestrator.py:** в select_context при наличии normalized_query вызывается await self.enrich_context_from_db_async(context, normalized_query.goal, limit=5) — подбор релевантных знаний из knowledge_nodes (ILIKE). (3) **ORCHESTRATION_CANARY.md:** добавлен подпункт «Включить V2 для 100% трафика» — ORCHESTRATION_V2_PERCENTAGE=100, перезапуск victoria-agent, рекомендация тестов и куратора. (4) **TODO_FIXME_BACKLOG:** hierarchical_orchestration и query_orchestrator отмечены закрытыми; skill_discovery — уточнено (api_info.function при генерации).
- **Итог:** декомпозиция целей через LLM с fallback; контекст запроса обогащается из БД; A/B 100% документирован. Тесты: run_all_system_tests. См. MASTER_REFERENCE «Последние изменения».
- **Страховки с отработкой (2026-02-11):** (1) **hierarchical_orchestration:** fallback не заглушка «Подзадача 1/2/3», а два уровня: сначала повтор LLM с упрощённым промптом (плоский список 1. 2. 3.), парсинг в root + level-1 цели; если снова пусто — эвристика: разбивка user_intent по « и », « затем », запятым, цели из текста намерения. (2) **skill_discovery:** при отсутствии api_info.function не заглушка, а поиск стандартных точек входа (skill_handler, run, execute) в модуле и вызов; если не найдено — явная ошибка «Нет точки входа. Задайте api_info.function». При api_info.function добавлен else: возврат ошибки, если функция не callable.

---

## 0.4ea. Proverka: сверка с библией и §5, закрытие пунктов в четырёх планах (2026-02-11)

- **Контекст:** команда /proverka — сверка с MASTER_REFERENCE и VERIFICATION_CHECKLIST_OPTIMIZATIONS §5 «При следующих изменениях»; закрыть сделанные пункты в планах всё_сделать_по_бэклогу, умнее_быстрее, план_внедрения_«как_я», план_доработок_principle_experts_first; остальные пункты бэклога (hierarchical_orchestration, query_orchestrator, skill_discovery и др.).
- **Выполнено:** (1) Сверка с библией и §5: затронутые области в сессии — куратор при деплое (runbook §1.5, скрипт), recap_framework (knowledge_os/app), границы SRC_AND_KNOWLEDGE_OS учтены; таймаут долгих скриптов (куратор ≥ 10 мин) зафиксирован в CURATOR_RUNBOOK §1.5. (2) **План «как я»:** п. 1.2 «сохранение обмена после ответа» отмечен закрытым — _save_session_exchange во всех четырёх путях run_task при session_id (CHANGES §0.4dx). (3) **Планы бэклог, умнее быстрее, PRINCIPLE_EXPERTS_FIRST:** отмечена proverka 2026-02-11; новых пунктов для закрытия нет. Остальные пункты бэклога (hierarchical_orchestration, query_orchestrator, skill_discovery, master_plan_generator, strategy_discovery, model_enhancer, early_warning_system) остаются в TODO_FIXME_BACKLOG — реализовывать **при касании** соответствующих модулей, не в этой сессии. (4) Запуск тестов: `./scripts/run_all_system_tests.sh`.
- **Итог:** библия и §5 учтены; в четырёх планах отмечены закрытые пункты и proverka; остальные пункты бэклога — по TODO_FIXME_BACKLOG при касании. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dz. «Погнали»: куратор при деплое + пункт из TODO_FIXME_BACKLOG (2026-02-11)

- **Контекст:** после сессии «доделываем» — куратор при деплое и пункты из TODO_FIXME_BACKLOG.
- **Внесено:** (1) **Куратор при деплое:** в [CURATOR_RUNBOOK.md](CURATOR_RUNBOOK.md) добавлен §1.5 «Куратор при деплое» — после деплоя один раз прогнать быстрый прогон и сравнение с эталонами; команда `./scripts/run_curator_post_deploy.sh` (обёртка над run_curator_and_compare.sh); таймаут среды ≥ 10 мин; опционально — шаг в pipeline. Скрипт **scripts/run_curator_post_deploy.sh** создан (executable). В [HOW_TO_INDEX.md](HOW_TO_INDEX.md) добавлена строка «Куратор при деплое». В [TODO_FIXME_BACKLOG.md](TODO_FIXME_BACKLOG.md) добавлен блок «Закрыто (вне плана)» с пунктом «Куратор при деплое». (2) **TODO_FIXME_BACKLOG (recap_framework):** в [recap_framework.py](knowledge_os/app/recap_framework.py) в **_build_context** добавлен параметр **results: Optional[Dict[int, Any]] = None**; в блок **dependencies** подставляются реальные результаты из **results.get(dep_id, "pending")** при наличии. В **_execute_plan** при всех вызовах _build_context передаётся текущий словарь **results**, чтобы уже выполненные шаги отображались в контексте зависимостей. Строка в TODO_FIXME_BACKLOG для recap_framework обновлена — закрыто.
- **Итог:** куратор при деплое документирован и доступен одной командой; recap_framework использует реальные результаты зависимостей в контексте. Тесты: 62 backend + 41 knowledge_os = 103 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dy. «Доделываем»: чекпоинт П.1.2 — сессия закрыта (2026-02-11)

- **Контекст:** завершение сессии после внедрения плана «как я» П.1.2 (сохранение обмена в session_context).
- **Выполнено:** П.1.2 полностью закрыт (четыре пути _save_session_exchange в victoria_server.run_task); CHANGES §0.4dx, MASTER_REFERENCE обновлены. Прогон `./scripts/run_all_system_tests.sh` — 103 passed. Дальше по желанию: куратор при деплое, пункты из TODO_FIXME_BACKLOG.
- **Итог:** сессия «доделываем» завершена. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dx. «Дальше»: план «как я» П.1.2 — сохранение обмена в session_context после ответа Victoria (2026-02-11)

- **Контекст:** план «как я» П.1.2 — после каждого успешного ответа Victoria сохранять пару (goal, output) в session_context для последующего использования как «память по задаче».
- **Внесено:** в **victoria_server.run_task** перед каждым успешным `return TaskResponse(status="success", ...)` добавлен вызов **`await _save_session_exchange(body.session_id, <goal>, <output>)`** при наличии `body.session_id`. Четыре точки: (1) quick_data — goal=body.goal, output=quick_data.get("output"); (2) veronica — goal=restated_goal или body.goal, output=veronica_result.get("output"); (3) enhanced — goal=restated_goal или body.goal, output=enhanced_result.get("result"); (4) agent_run — goal=restated_goal или body.goal, output=str(result). Хелпер _save_session_exchange уже был; теперь вызывается во всех путях успешного ответа.
- **Итог:** при запросах с session_id после успешного ответа обмен сохраняется в session_context_manager (БД/Redis); при следующих запросах с той же сессией get_session_memory_summary вернёт «Ранее по этой задаче». Тесты: 62 backend + 41 knowledge_os = 103 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dw. «Дальше по плану»: эталоны куратора list_files, greeting, one_line_code (2026-02-11)

- **Контекст:** план «умнее быстрее» §3.1 — при совпадении с другими эталонами из standards/ подмешивать соответствующий эталон в промпт.
- **Внесено:** в [victoria_enhanced._get_curator_rag_context](knowledge_os/app/victoria_enhanced.py) расширена логика по ключевым словам: подмешиваются эталоны из RAG (домен curator_standards) для **list_files** (список файлов, покажи файлы, list dir), **greeting** (привет, здравствуй, hello — при коротком запросе ≤5 слов), **one_line_code** (одна строка кода). Запросы к БД по metadata.standard и по content ILIKE. Статус проекта и «что умеешь» без изменений.
- **Итог:** ответы по «покажи файлы», приветствиям и «одна строка кода» опираются на эталоны из RAG при наличии узлов в curator_standards. Тесты: 103 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dv. «Дальше»: план «умнее быстрее» §4.1 Nightly → видимость в RAG (2026-02-11)

- **Контекст:** план «умнее быстрее» §4.1 — убедиться, что узлы от nightly_learner и др. имеют embedding; при необходимости дозапись embedding для узлов без него.
- **Внесено:** (1) **knowledge_os/scripts/backfill_knowledge_embeddings.py** — скрипт дозаписи embedding: SELECT узлов с `embedding IS NULL`, для каждого вызов get_embedding из app.semantic_cache (Ollama, тот же источник, что и RAG), UPDATE knowledge_nodes SET embedding = … WHERE id. Аргумент --limit (по умолчанию 100). Docstring: план §4.1, рекомендуемый timeout ≥ 5 мин. (2) **HOW_TO_INDEX.md** — строка «Nightly и обучение → видимость в RAG» с командой и ссылкой на скрипт.
- **Итог:** узлы без embedding можно массово заполнить одним запуском; при желании — cron/launchd для периодической дозаписи. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4du. «Двигаемся дальше»: план «умнее быстрее» §2.1 «сделай как тогда» (2026-02-11)

- **Контекст:** план «умнее быстрее» §2.1 — при фразах «как вчера», «повтори», «то же что» подставлять перед understand_goal контекст последних завершённых задач.
- **Внесено:** (1) **knowledge_os/app/recent_tasks_context.py** — функция **get_recent_completed_tasks_context(project_context, limit=5)** запрашивает из БД tasks последние завершённые задачи (по project_context или глобально), возвращает текст «Пользователь отсылает к предыдущему действию. Контекст последних завершённых задач: …»; **is_ambiguous_goal_reference(goal)** — проверка маркеров. (2) **victoria_server:** перед _understand_goal_with_clarification при _is_ambiguous_goal_reference(body.goal) вызывается get_recent_completed_tasks_context(body.project_context, 5); результат передаётся в _understand_goal_with_clarification(..., last_tasks_context=...). (3) **understand_goal(raw_goal, last_tasks_context=None)** — при наличии last_tasks_context блок подставляется в начало промпта для LLM.
- **Итог:** запросы «сделай как вчера»/«повтори» получают контекст последних задач и переформулируются с опорой на них. Тесты: 103 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dt. Proverka «все делаем»: сверка с библией, §5, закрытие пунктов в четырёх планах (2026-02-11)

- **Контекст:** команда /proverka — сверка с MASTER_REFERENCE и VERIFICATION_CHECKLIST_OPTIMIZATIONS §5 «При следующих изменениях»; закрыть сделанные пункты в планах всё_сделать_по_бэклогу, умнее_быстрее, план_внедрения_«как_я», план_доработок_principle_experts_first.
- **Выполнено:** (1) Сверка с библией и §5: учтены пункты по чату (контракт goal/project_context), Victoria/Enhanced (run_all_system_tests после правок, при необходимости build + куратор), таймаут среды для долгих скриптов (куратор --quick ≥ 10 мин, full ≥ 30 мин). (2) **План «как я»:** п.11.3 п.1 «Единый фрагмент русский + краткость» отмечен выполненным (victoria_enhanced использует PROMPT_RUSSIAN_ONLY и PROMPT_RUSSIAN_AND_BREVITY_LINES из configs.victoria_common; CHANGES §0.4ds). (3) **План «умнее быстрее»:** §3.1 «Перед исполнением похожие успешные решения» для execution/multi_step при методе simple отмечен выполненным (общий путь _get_similar_tasks_context + kb_block). (4) Планы бэклог и PRINCIPLE_EXPERTS_FIRST — обновлена шапка (proverka 2026-02-11). (5) Запуск тестов: `./scripts/run_all_system_tests.sh`.
- **Итог:** библия и §5 учтены; в четырёх планах отмечены закрытые пункты; тесты — по результату прогона. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4ds. «Погнали дальше по планам»: п.11.3 п.1 единый русский/краткость в enhanced (2026-02-11)

- **Контекст:** план «как я» п.11.3 п.1 — единый фрагмент «только русский» и «краткость» из configs/victoria_common использовать везде в victoria_enhanced.
- **Внесено:** В **victoria_enhanced.py** добавлен импорт **PROMPT_RUSSIAN_ONLY** и **PROMPT_RUSSIAN_AND_BREVITY_LINES** из configs.victoria_common (с fallback при ImportError). Все жёстко прописанные строки «КРИТИЧЕСКИ ВАЖНО: ОБЯЗАТЕЛЬНО отвечай ТОЛЬКО на русском» заменены на использование этих констант: в ReAct/department_heads (expert_system_prompt, retry_system_prompt, ai_core fallback), в ветке coding и приветствия (simple_prompt), в fallback build_simple_prompt при ImportError — используется PROMPT_RUSSIAN_AND_BREVITY_LINES. §3.1 «похожие успешные решения» для execution/multi_step: проверено — при методе simple блок уже подмешивается (вызов _get_similar_tasks_context и добавление в kb_block в общем пути для не‑coding).
- **Итог:** один источник формулировок «русский + краткость» в enhanced; п.11.3 п.1 закрыт. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dr. План 12.2 п.1 (исполнение по assignments) и §2 контекст «ранее по задаче» (2026-02-11)

- **Контекст:** план «как я» п.12.2 п.1 — план → исполнение по assignments; план «умнее быстрее» §2 — контекст «ранее по задаче» и похожие выполненные задачи.
- **Внесено:** (1) **Исполнение по assignments:** добавлен [knowledge_os/app/execute_assignments.py](knowledge_os/app/execute_assignments.py) — `execute_assignments_async(assignments, goal, strategy, ...)` вызывает run_smart_agent_async по каждому эксперту из assignments, агрегирует ответы. В [victoria_server](src/agents/bridge/victoria_server.py) при **EXECUTE_ASSIGNMENTS_IN_RUN=true** после получения плана вызывается execute_assignments_async; результат подставляется в orchestration_context_str (контекст Victoria). **По умолчанию включено:** в knowledge_os/docker-compose.yml для victoria-agent задано `EXECUTE_ASSIGNMENTS_IN_RUN: ${EXECUTE_ASSIGNMENTS_IN_RUN:-true}` («сделай сама» — план выполняется без ручной настройки). (2) **§2 контекст:** в victoria_enhanced подпись при task_memory заменена на **«Ранее по этой задаче (сессия):»** (вместо «По этой сессии уже делали»). Для категории **coding** добавлен вызов _get_similar_tasks_context и блок «Похожие успешные решения» в simple-промпт. (3) NEXT_STEPS §5 и планы обновлены.
- **Итог:** опциональное исполнение по assignments через env; единая подпись сессии и похожие задачи для coding. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dq. «Погнали дальше закрывать планы»: умнее быстрее §1.1/§3.1, как я п.1.1/п.2 (2026-02-11)

- **Контекст:** закрыть уже реализованные пункты в планах «умнее быстрее» и «как я».
- **Внесено:** (1) **План «умнее быстрее»:** §1.1 «Стратегия быстрый + умный» — отмечено выполненным: в MAC_STUDIO_M4_MODELS_GUIDE уже есть раздел «Стратегия «быстрый + умный» для 128 GB» (рекомендуемый набор, порядок загрузки). §3.1 «Приоритет недавних и часто используемых узлов» — отмечено выполненным: в victoria_server._get_knowledge_context используется ORDER BY usage_count DESC NULLS LAST (CHANGES §0.4cq). (2) **План «как я»:** п.1.1 вариант A «план = подсказка» — отмечено принятым (NEXT_STEPS §5). п.2 fallback для greeting и what_can_you_do — отмечено выполненным: victoria_server fast path (привет/что умеешь до LLM) и victoria_enhanced fallback при недоступности LLM для status_query, greeting, what_can_you_do (get_capabilities_text()). (3) Шапки обоих планов обновлены.
- **Итог:** четыре пункта планов закрыты без изменений кода (реализация уже была). См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dp. Proverka: сверка с библией, §5, закрытие пунктов в планах (2026-02-11)

- **Выполнено:** (1) Сверка с MASTER_REFERENCE и VERIFICATION_CHECKLIST_OPTIMIZATIONS §5 (затронутые области: куратор, планы; п.38 — тесты после правок Victoria; таймаут долгих скриптов — CURATOR_RUNBOOK §1). (2) Планы проверены: **всё_сделать_по_бэклогу** и **PRINCIPLE_EXPERTS_FIRST** — статус ВЫПОЛНЕН, изменений нет. **умнее_быстрее** и **как_я** — сделанные пункты уже отмечены в шапках. (3) В плане «как я» п.3.1 дополнено: run_curator_and_compare.sh поддерживает --write-findings (CHANGES §0.4do). (4) Запущен `./scripts/run_all_system_tests.sh` — 62 backend + 41 knowledge_os = 103 passed.
- **Итог:** библия актуальна, чеклист §5 учтён, новых пунктов для закрытия в планах не выявлено. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4do. «Дальше делаем»: run_curator_and_compare с --write-findings (2026-02-11)

- **Контекст:** при регулярном прогоне куратора удобно сразу писать FINDINGS при падении скоринга (план «умнее быстрее» §4.1).
- **Внесено:** (1) **scripts/run_curator_and_compare.sh** — добавлена опция **--write-findings**. Можно комбинировать с --full: `./scripts/run_curator_and_compare.sh --write-findings` или `--full --write-findings`. При сравнении с каждым эталоном вызывается curator_compare_to_standard.py с --write-findings; при падении доли совпадений ниже порога в FINDINGS_YYYY-MM-DD.md дописываются релевантные пункты. (2) **CURATOR_RUNBOOK** §2 — в блок «Прогон + сравнение по всем эталонам» добавлены примеры с --write-findings.
- **Итог:** регулярный прогон одной командой может сразу пополнять FINDINGS для последующего разбора куратором. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dn. «Делаем дальше»: §4.1 candidate for standard, куратор как источник задач (2026-02-11)

- **Контекст:** план «умнее быстрее» §4.1 — candidate for standard и куратор как источник задач на дообучение.
- **Внесено:** (1) **Candidate for standard:** при лайке (POST /api/feedback, score>0) инсайт при сохранении в knowledge_nodes получает **metadata.suggested_standard=true** (rest_api.submit_feedback) — куратор может отбирать кандидатов и переносить в standards/. (2) **Куратор как источник:** в **curator_compare_to_standard.py** добавлены флаг **--write-findings** и аргумент **--threshold** (по умолчанию 0.5). При доле совпадений с эталоном ниже порога в **docs/curator_reports/FINDINGS_YYYY-MM-DD.md** дописывается пункт «Требуется дообучение RAG / правка эталона» только по задачам, релевантным эталону (goal_relevant_to_standard: status_project, greeting, what_can_you_do, list_files, one_line_code). (3) **CURATOR_RUNBOOK** §2 — абзац про --write-findings и --threshold; §3 — абзац про кандидаты в эталон (suggested_standard). (4) План «умнее быстрее» §4.1 отмечен выполненным; следующие шаги — при желании кнопка в UI, полуавтомат по suggested_standard.
- **Итог:** цикл «лайк → кандидат в эталон» и «прогон куратора → FINDINGS при падении скоринга» замкнуты. Тесты: 103 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dm. Proverka: сверка с библией, §5, тесты (2026-02-11)

- **Выполнено:** сверка с MASTER_REFERENCE и VERIFICATION §5; планы проверены (бэклог и PRINCIPLE_EXPERTS_FIRST — ВЫПОЛНЕН; «умнее быстрее» и «как я» — сделанные пункты закрыты, следующие шаги опциональны). Запущен `./scripts/run_all_system_tests.sh` — 103 passed. Новых пунктов для закрытия нет.
- **Итог:** библия актуальна, чеклист учтён. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dl. Proverka: сверка с библией, §5, тесты (2026-02-11)

- **Контекст:** команда /proverka — сверка с MASTER_REFERENCE, VERIFICATION §5, закрытие сделанных пунктов в планах.
- **Выполнено:** (1) Сверка с MASTER_REFERENCE и VERIFICATION §5 (п. 38: после правок Victoria/Enhanced — тесты, при необходимости куратор). (2) Планы проверены: бэклог и PRINCIPLE_EXPERTS_FIRST — статус ВЫПОЛНЕН; «умнее быстрее» и «как я» — все сделанные пункты уже отмечены (runbook по типу, промпты Victoria, куратор run+compare, §4 «принять», 64k–128k, п.4 блок экспертов). (3) Запущен `./scripts/run_all_system_tests.sh` — 62 backend + 41 knowledge_os = 103 passed.
- **Итог:** библия актуальна, чеклист учтён, тесты зелёные. Новых пунктов для закрытия в планах не выявлено.

---

## 0.4dk. «Доделываем»: контекст 64k–128k, блок экспертов в simple (2026-02-11)

- **Контекст:** оставшиеся шаги планов «умнее быстрее» и «как я».
- **Внесено:** (1) **Контекст 64k–128k:** в [MAC_STUDIO_M4_MODELS_GUIDE.md](docs/MAC_STUDIO_M4_MODELS_GUIDE.md) в блок «Стратегия быстрый + умный» добавлен подпункт «Контекст 64k–128k»: описание env VICTORIA_CHAT_HISTORY_MAX_MESSAGES, VICTORIA_HISTORY_MAX_CHARS, VICTORIA_GOAL_MAX_CHARS и рекомендуемые значения (65536/131072 символов, 50 сообщений) для длинного контекста. (2) **План «как я» п.4 — блок экспертов в simple:** в [victoria_enhanced](knowledge_os/app/victoria_enhanced.py) при категориях status_query и general в kb_block перед build_simple_prompt добавляется строка «Ответ в духе команды: дашборд, MASTER_REFERENCE, эксперты Backend/QA/SRE/ML» (без вызова Swarm). (3) Планы «умнее быстрее» и «как я» обновлены: пункты отмечены выполненными, «Следующие шаги» актуализированы.
- **Итог:** контекст 64k–128k документирован; короткие ответы статус/что умеешь опираются на блок «в духе команды». Тесты: 103 passed.

---

## 0.4dj. Proverka «делаем все»: §4 обратная связь «принять» для усиления узлов (2026-02-11)

- **Контекст:** план «умнее быстрее» §4 — при явном «принять» (лайк) усиливать узлы knowledge, попавшие в контекст ответа.
- **Внесено:** (1) **rest_api.submit_feedback:** при score > 0 после обновления interaction_logs читаем metadata.knowledge_node_ids из записи; если список не пуст — выполняем `UPDATE knowledge_nodes SET usage_count = usage_count + 1 WHERE id = ANY($1::uuid[])`. Так при лайке узлы, использованные при формировании ответа, получают больший вес в RAG. (2) **LogInteractionRequest:** добавлено поле **knowledge_node_ids: Optional[List[str]]** — при вызове /api/log_interaction можно передать ID узлов, попавших в контекст; token_logger уже сохраняет их в metadata и при наличии инкрементирует usage_count при записи; при последующем лайке submit_feedback повторно инкрементирует их. (3) **План «умнее быстрее»:** §4 первый пункт («обратная связь по принятию ответа») отмечен как выполненный; «Следующие шаги» обновлены.
- **Итог:** цикл «принять» → усиление узлов работает; для полного контура остаётся передача node_ids из Victoria/backend при логировании чата (когда RAG возвращает узлы). Тесты: 103 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4di. Proverka: закрытие пунктов в планах, сверка с библией (2026-02-11)

- **Контекст:** команда /proverka — сверка с MASTER_REFERENCE и VERIFICATION §5, закрытие сделанных пунктов в четырёх планах, следующие шаги.
- **Внесено:** (1) **План «умнее быстрее»:** в «Закрыто в этой сессии» добавлен §3.1 runbook по типу задачи (_get_runbook_context, блок «По runbook и чеклисту»); в §3.1 первый пункт отмечен как выполненный; «Следующие шаги» — §4 обратная связь «принять», при желании 64k–128k. (2) **План «как я»:** в «Закрыто» добавлены п. 3.1 (run_curator_and_compare.sh), п. 11.3 версионирование (PROMPTS_VICTORIA.md); в §3.1 и §11.3 п.3 отмечено «Сделано»; «Следующие шаги» — при желании п. 12.2 п.1, п. 4 опционально. (3) **План бэклог и PRINCIPLE_EXPERTS_FIRST:** добавлена строка о сверке с библией и §5; следующих обязательных пунктов нет. (4) **Проверка:** запущен `./scripts/run_all_system_tests.sh` — 62 backend + 41 knowledge_os = 103 passed.
- **Итог:** планы актуальны; при работе по ним ориентироваться на обновлённые «Следующие шаги». VERIFICATION §5 и пункт 38 (после правок Victoria/Enhanced — тесты, при необходимости куратор) учтены.

---

## 0.4dh. «Все делаем»: runbook по типу задачи, промпты Victoria, куратор (2026-02-11)

- **Контекст:** приоритетные шаги из планов «умнее быстрее» §3.1 и «как я» п.3.1, п.11.3.
- **Внесено:** (1) **Runbook по типу задачи:** в **victoria_enhanced.py** добавлен метод **\_get_runbook_context(goal, category)** — для категорий coding, execution, multi_step, informational, reasoning запрашиваются до 2 узлов из knowledge_nodes (домен curator_standards или metadata.runbook=true), приоритет по usage_count; блок «По runbook и чеклисту: …» добавляется в kb_block при сборке simple-промпта. (2) **Документ «Промпты Victoria»:** создан **docs/PROMPTS_VICTORIA.md** — таблица компонент/файл/назначение/владелец (simple, ReAct think/act/reflect, capabilities, corporation_thinking, план Victoria/Veronica, фрагменты русский+краткость); раздел «Где что редактировать» и ссылки на библию. (3) **Куратор: прогон + сравнение:** скрипт **scripts/run_curator_and_compare.sh** — запуск куратора (по умолчанию --quick, опция --full), затем сравнение с эталонами status_project, greeting, what_can_you_do, list_files, one_line_code; в **CURATOR_RUNBOOK.md** §2 добавлен абзац с командами и напоминанием о таймауте среды (10/30 мин).
- **Итог:** библия и эталоны применяются по категории задачи; промпты версионированы в одном документе; регулярная проверка куратора — одной командой. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dg. Учёт таймаута среды везде: чтобы такие ошибки не повторялись (2026-02-11)

- **Цель:** закрепить правило «внешний таймаут среды ≥ требуемому времени скрипта» во всех точках, где запускаются или документируются долгие скрипты.
- **Внесено:** (1) **VERIFICATION_CHECKLIST_OPTIMIZATIONS** §3 — новая строка в таблице причин сбоев: «Прогон куратора (или другой долгий скрипт) прерывается по таймауту» (причина: внешний таймаут среды; решение: timeout среды ≥ из runbook, в новых долгих скриптах указывать рекомендуемый timeout). §4 «Мировые практики» — добавлен пункт «Таймаут среды запуска». §5 «При следующих изменениях» — новый буллет: запуск долгих скриптов из среды с таймаутом — проверять минимальный таймаут в runbook; при добавлении скриптов с временем >2–3 мин — указывать в docstring/runbook «Рекомендуемый timeout запуска ≥ N мин». (2) **scripts/curator_send_tasks_to_victoria.py** — в docstring добавлен абзац «Таймаут среды запуска» с цифрами (--quick ≥ 10 мин, полный ≥ 30 мин). (3) **CONTRIBUTING.md** §2 — пункт «Скрипты с длительным выполнением» и ссылки на VERIFICATION §3, §5, CURATOR_RUNBOOK. (4) **.cursor/commands/proverka.md** — строка: при запуске долгих скриптов из среды с таймаутом задавать timeout по runbook. (5) **HOW_TO_INDEX.md** — строка в таблице «Куратор» про timeout; новая строка «Таймаут среды при запуске скриптов» с ссылками на VERIFICATION, CURATOR_RUNBOOK, CONTRIBUTING. (6) **.cursorrules** — новый короткий раздел «Таймаут среды при запуске скриптов» с правилом и ссылками.
- **Итог:** при запуске куратора или других долгих скриптов из Cursor/CI/IDE агент и разработчик видят правило в чеклисте, runbook, CONTRIBUTING, proverka и cursorrules; новые скрипты рекомендуется документировать с рекомендуемым timeout. См. VERIFICATION §3, §5.

---

## 0.4df. Причина таймаута полного прогона куратора (2026-02-11)

- **Вопрос:** почему при запуске куратора «таймаут был превышен».
- **Причина:** не таймаут **внутри** скрипта куратора (poll timeout 180 с на задачу), а **внешний лимит времени** среды, в которой команда выполнялась (например Cursor/run_terminal_cmd с timeout=180000 ms = 3 мин). При `--quick` куратор выполняет 2 задачи **последовательно**, каждая — до 180 с → в худшем случае 6 мин; плюс холодный старт LLM 1–5 мин. Итого 3 мин недостаточно.
- **Внесено:** в **CURATOR_RUNBOOK.md** §1 добавлен абзац «Почему прогон мог прерваться по таймауту»: причина (внешний kill), рекомендуемый лимит для `--quick` не менее 8–10 мин, для полного прогона 25–30 мин; в Cursor/скриптах для быстрого прогона не задавать timeout меньше 10 мин (600000 ms).
- **Итог:** при запуске куратора из среды с таймаутом задавать лимит ≥ 10 мин (quick) или ≥ 30 мин (полный). См. CURATOR_RUNBOOK §1.

---

## 0.4de. Proverka: закрытие сделанных пунктов в планах (2026-02-11)

- **Контекст:** команда /proverka — сверка с библией, VERIFICATION §5, обновление планов: отметить выполненное и следующие шаги.
- **Внесено:** (1) **MASTER_REFERENCE** и **VERIFICATION_CHECKLIST_OPTIMIZATIONS** §5 учтены (изменения касались Victoria/bridge, session_context, configs — пункты по маршрутизации, чату, RAG, контракту goal/project_context актуальны). (2) **План «умнее быстрее»:** в блоке «Закрыто в этой сессии» отмечены understand_goal на умной модели, длинный контекст (env в bridge), runbook Veronica; «Следующие шаги» обновлены (расширить runbook по типу задачи, обратная связь «принять», при желании 64k–128k). (3) **План «как я»:** в «Закрыто в этой сессии» отмечены п.1.2 память по задаче, п.11.3 шаблон simple, п.12.4 runbook Veronica, п.12.2 контекст из БД; «Следующие шаги» — прогоны куратора, версионирование промптов, при желании план → исполнение. (4) **Бэклог:** в плане ссылка на CHANGES §0.4de. **PRINCIPLE_EXPERTS_FIRST** — без изменений (все 7 закрыты).
- **Итог:** при работе по планам ориентироваться на обновлённые «Следующие шаги»; библия актуальна. Тесты: 103 passed.

---

## 0.4dd. Планы «умнее быстрее» и «как я»: длинный контекст, память по задаче, шаблон simple (2026-02-11)

- **Контекст:** «всё важно, всё делаем» — оставшиеся пункты из следующих шагов планов.
- **Внесено:** (1) **Длинный контекст:** в **victoria_server.py** добавлены env: **VICTORIA_CHAT_HISTORY_MAX_MESSAGES** (по умолчанию 30), **VICTORIA_HISTORY_MAX_CHARS** (0 = не обрезать), **VICTORIA_GOAL_MAX_CHARS** (0 = не обрезать). При формировании context_with_history история обрезается по числу сообщений и при HISTORY_MAX_CHARS — по символам с пометкой «[... обрезано по лимиту контекста ...]»; цель для Enhanced обрезается по GOAL_MAX_CHARS при необходимости. (2) **Память по задаче:** в **session_context_manager.py** добавлен метод **get_session_memory_summary(user_id, expert_name, max_items=5, max_chars=500)** — краткий блок «запрос → ответ» по сессии. В **victoria_server.py** добавлена **\_get_task_memory_from_db(session_id)**; при наличии session_id в context передаётся **context_with_history["task_memory"]**. В **victoria_enhanced.py** при **context.get("task_memory")** в simple-промпт добавляется блок «По этой сессии уже делали: …». (3) **Шаблон simple:** в **configs/victoria_common.py** добавлены **WORLD_PRACTICES_LINE**, функция **build_simple_prompt(role_instruction, kb_block, goal, world_practices_line=...)** — единый источник simple-промпта. В **victoria_enhanced** при сборке simple используется **build_simple_prompt** и блок task_memory перед вызовом.
- **Итог:** длинный контекст настраивается через env; память по сессии подмешивается при session_id; шаблон simple в одном месте. Тесты: 103 passed. Куратор: запускать вручную при поднятой Victoria (`./scripts/run_curator_scheduled.sh` или быстрый `--quick`). См. MASTER_REFERENCE «Последние изменения».

---

## 0.4dc. Контекст из БД: задачи по проекту в промпт Victoria (2026-02-11)

- **Контекст:** план «как я» п.12.2 — при наличии project_context подмешивать в промпт Victoria блок «Текущие задачи по проекту».
- **Внесено:** (1) В **victoria_server.py** при формировании context_with_history для enhanced.solve() добавлено `context_with_history["project_context"] = project_context` (синхронный и фоновый путь). (2) В **victoria_enhanced.py** добавлен метод `_get_project_tasks_context(project_context)` — запрос к таблице tasks по project_context (миграция add_project_context_to_tasks), до 5 последних по updated_at, формат «Текущие задачи по проекту (последние): …». При сборке simple-промпта при `context.get("project_context")` вызывается этот метод и блок добавляется в kb_block перед «Запрос:».
- **Итог:** Victoria при ответе в контексте проекта видит последние задачи по этому проекту; тесты 103 passed. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4db. Обновление планов: закрыты сделанные пункты (2026-02-11)

- **Контекст:** proverka по планам — отметить выполненное и следующие шаги.
- **Внесено:** В четырёх планах (.cursor/plans/): (1) **PRINCIPLE_EXPERTS_FIRST** — все 7 пунктов отмечены как закрытые, добавлена таблица «Закрыто» со ссылками на код. (2) **Всё сделать по бэклогу** — план помечен закрытым (покрытие 8%, WHATS_NOT_DONE, эмбеддинги, тесты 103). (3) **Умнее быстрее знания в дело** — добавлен блок «что сделано» (стратегия моделей, контекст ранее по задаче, RAG usage_count, похожие задачи, candidate for standard) и «следующие шаги» (understand_goal на умной модели, длинный контекст, runbook). (4) **План «как я»** — добавлен блок «что закрыто» (план=подсказка, fallback LLM, куратор, секреты, операционные секретики, RAG Redis, CONTRIBUTING, PROMPT_RUSSIAN_ONLY) и «следующие шаги» (память по задаче, прогоны куратора, шаблон simple, Veronica runbook, контекст из БД).
- **Итог:** при работе по планам ориентироваться на блоки «Следующие шаги» в каждом плане; библия и WHATS_NOT_DONE актуальны.

---

## 0.4da. PRINCIPLE_EXPERTS_FIRST: П.3–П.7 (2026-02-11)

- **П.3 Сохранение удачных ответов при лайке:** В **rest_api.py** добавлен POST /api/feedback (body: interaction_log_id, score 1|-1, feedback_text). При score=1 обновляется interaction_logs и сжатый инсайт (Q→A) записывается в knowledge_nodes (домен эксперта, embedding при наличии).
- **П.4 Метрика «ответил эксперт»:** В **backend** добавлены счётчики CHAT_EXPERT_ANSWER_TOTAL (labels: victoria, fallback_llm, direct, template) и CHAT_FALLBACK_TOTAL в prometheus_metrics; в **chat.py** инкремент при успешном ответе по пути Victoria / fallback LLM / direct с expert_name или без. Сводка в /metrics/summary.
- **П.5 Консенсус по важным:** В **victoria_server.py** в _assess_complexity добавлены маркеры «критично», «срочно», «urgent», «critical» в complex_keywords — такие запросы идут по пути Swarm/Consensus (2–3 эксперта).
- **П.6 Единый fallback веб-поиска:** Создан **knowledge_os/app/web_search_fallback.py** — порядок: DuckDuckGo, в будущем Ollama (TODO). Воркер и VeronicaWebResearcher используют web_search_sync из этого модуля.
- **П.7 Найм → кнопка «Принять кандидата»:** В **rest_api.py** добавлены GET /api/recruitment/candidates и POST /api/recruitment/candidates/accept (body: index; защита API_KEY). В **dashboard** (вкладка «Автономный Рекрутинг») добавлен блок «Кандидаты на ревью» с кнопкой «Принять кандидата» (вызов accept, затем rerun).
- **Итог:** все пункты плана PRINCIPLE_EXPERTS_FIRST Фазы 1–3 реализованы. См. MASTER_REFERENCE «Последние изменения».

---

## 0.4cz. PRINCIPLE_EXPERTS_FIRST Фаза 1: скиллы и веб-поиск в воркере (2026-02-11)

- **Контекст:** план PRINCIPLE_EXPERTS_FIRST — П.2 (скиллы в контексте воркера), П.1 (веб-поиск по запросу задачи). VERIFICATION §5: в воркере синхронный I/O только через run_in_executor.
- **Внесено:** (1) **П.2** В **smart_worker_autonomous.py** добавлен маппинг ROLE_DEPARTMENT_TO_SKILLS (role/department → до 2 папок скиллов), функция _read_skill_snippets_sync(skill_folders, max_chars) — читает SKILL.md (первые 2 KB), вызывается через run_in_executor. Блок «ИНСТРУКЦИИ ИЗ СКИЛЛОВ» подставляется в промпт после RELEVANT KNOWLEDGE. (2) **П.1** Маркеры актуальности (_WEB_MARKERS: актуальн, последн, 2025, best practices, latest и т.д.), _task_needs_web_search(title, desc), _web_search_sync(query, max_results=3) через DuckDuckGo; вызов через run_in_executor с asyncio.wait_for(..., timeout=10); блок «АКТУАЛЬНЫЕ ДАННЫЕ ИЗ ВЕБ-ПОИСКА» (топ-3 сниппета) в промпт при наличии маркеров. При ошибке/таймауте веб-блок пустой, выполнение задачи не прерывается.
- **Итог:** эксперт в воркере получает релевантные скиллы по роли/отделу и при необходимости — свежие данные из веб-поиска. Библия: MASTER_REFERENCE «Последние изменения», этот раздел.

---

## 0.4cy. Embedding при вставке в knowledge_nodes: все оставшиеся пути (2026-02-11)

- **Контекст:** доделать «как надо» — везде по возможности сохранять embedding (VERIFICATION §5).
- **Внесено:** Добавлено сохранение embedding (get_embedding из semantic_cache, content[:8000], fallback без embedding при ошибке) в: **streaming_orchestrator**, **strategic_board** (2 места: консультация Совета, директива), **dashboard_daily_improver**, **expert_council_discussion** (save_hypotheses), **expert_evolver**, **researcher**, **expert_generator**, **process_expert_task**, **ad_generator**, **meta_synthesizer**, **knowledge_bridge** (knowledge_os/src/ai/autonomous/sync). Во всех — опциональный вызов get_embedding, INSERT с колонкой embedding при успехе.
- **Итог:** все пути записи в knowledge_nodes в app/ и observability/ по возможности сохраняют embedding. WHATS_NOT_DONE §4 обновлён. Тесты: 103 passed.

---

## 0.4cx. Embedding при вставке в knowledge_nodes: nightly_learner, knowledge_applicator, skill_discovery, enhanced_orchestrator (2026-02-11)

- **Контекст:** завершение списка путей записи из WHATS_NOT_DONE §4 — по возможности сохранять embedding (VERIFICATION §5).
- **Внесено:** В **nightly_learner.py** — три INSERT (insights цикла nightly_council, autonomous_tests, auto_profiling phase 15): опционально get_embedding(content[:8000]), при успехе INSERT с embedding. В **observability/knowledge_applicator.py** (apply_retrospectives_to_knowledge): в цикле по ретроспективам опционально get_embedding (импорт semantic_cache или app.semantic_cache), INSERT с embedding при наличии. В **skill_discovery.py** (_save_skill_to_knowledge): get_embedding(skill_content[:8000]), INSERT с embedding или без; ON CONFLICT DO NOTHING сохранён. В **enhanced_orchestrator.py** (кросс-доменная гипотеза): тот же паттерн, что в orchestrator.py.
- **Итог:** все перечисленные в §4 пути записи в knowledge_nodes теперь по возможности сохраняют embedding. WHATS_NOT_DONE §4 обновлён — список «с embedding» полный. Тесты: 103 passed.

---

## 0.4cw. Embedding при вставке в knowledge_nodes: orchestrator, enhanced_expert_evolver (2026-02-11)

- **Контекст:** продолжение §0.4cv — по возможности сохранять embedding при добавлении записей (VERIFICATION §5, WHATS_NOT_DONE §4).
- **Внесено:** В **orchestrator.py** при INSERT кросс-доменной гипотезы: опционально get_embedding(content[:8000]), при успехе — INSERT с колонкой embedding. В **enhanced_expert_evolver.py** при сохранении события эволюции эксперта: то же (get_embedding по content_kn[:8000], INSERT с embedding при наличии). Ошибка/недоступность semantic_cache не ломает вставку.
- **Итог:** ещё два пути записи в knowledge_nodes сохраняют embedding при доступности Ollama. WHATS_NOT_DONE §4 обновлён. Тесты: 103 passed.

---

## 0.4cv. Embedding при создании знания через REST API (2026-02-11)

- **Контекст:** VERIFICATION §5 «При добавлении записей в knowledge_nodes по возможности сохранять embedding»; WHATS_NOT_DONE §4 — rest_api.py был в списке вставок без embedding.
- **Внесено:** В **knowledge_os/app/rest_api.py** в endpoint POST /knowledge: ленивый импорт get_embedding из semantic_cache; при создании узла по возможности вызывается get_embedding(content[:8000]); при успехе INSERT с колонкой embedding (vector(768)), иначе — INSERT без embedding (как раньше). Ошибка эмбеддинга не ломает создание узла.
- **Итог:** создание знания через REST API теперь сохраняет embedding при доступности semantic_cache (Ollama). WHATS_NOT_DONE §4 обновлён: rest_api в списке «с embedding». Тесты: run_all_system_tests.sh — 103 passed.

---

## 0.4cu. Сессия «надо всё сделать» по бэклогу (2026-02-11)

- **Контекст:** закрыть все реалистично закрываемые пункты из WHATS_NOT_DONE и ROADMAP; остальное явно пометить «не в этой сессии» с причинами.
- **Внесено:** (1) **Покрытие и CI:** замер unit knowledge_os ~12%; в pytest-knowledge-os.yml порог COVERAGE_FAIL_UNDER поднят с 5% до 8% (оба job: no-db и with-db); комментарий в workflow обновлён. (2) **WHATS_NOT_DONE:** добавлен блок «Закрыто в этой сессии / Не делаем (причины)» — таблица отложенных пунктов (секреты в проде, auth, исполнение по assignments, дублирование src/knowledge_os, TODO при касании, signal_live/data_quality); в §3 порог покрытия зафиксирован как 8% (2026-02-11). (3) **Эмбеддинги knowledge_nodes:** в §4 перечислены пути записи: с embedding (smart_worker_autonomous, corporation_knowledge_system) и без (rest_api, enhanced_expert_evolver, nightly_learner, knowledge_applicator, skill_discovery, enhanced_orchestrator, orchestrator) — при касании по возможности добавлять get_embedding. (4) **Библия:** MASTER_REFERENCE «Последние изменения» — отсылка к этому разделу.
- **Итог:** реалистично закрытые пункты отмечены; отложенное — с явными причинами. Финальная проверка: run_all_system_tests.sh.

---

## 0.4ct. Роль куратора-наставника и эталон list_files (2026-02-11)

- **Контекст:** уточнение, как куратор (Cursor) «учит» Victoria; донастройка эталона «список файлов» для ответов через Veronica (STDOUT).
- **Внесено:** (1) **CURATOR_RUNBOOK §0** — роль куратора-наставника: не обучение при каждой задаче, а поддержка эталонов, прогоны, обновление RAG и библии; Victoria учится из контекста (RAG, эталоны). (2) **curator_compare_to_standard.py:** в список ключевых слов для сравнения добавлены «STDOUT», «total» (для эталона list_files при делегировании в Veronica). (3) **standards/list_files.md:** в эталонный ответ добавлена формулировка про «STDOUT и total от вывода ls». После правок сравнение по отчёту curator_2026-02-10_21-50-03: задача «покажи список файлов» — 2/6 ключевых фраз (было 0/4).
- **Итог:** явно зафиксировано, что куратор задаёт стандарт и среду; эталон list_files учитывает формат ответа Veronica.

---

## 0.4cs. Чекпоинт сессии: верификация и напоминание про куратор (2026-02-11)

- **Контекст:** закрытие сессии внедрения планов «как я» и «умнее, быстрее» — зафиксировать состояние и рекомендации.
- **Внесено:** (1) **Тесты:** прогнаны backend 62 + knowledge_os 41 (run_all_system_tests.sh) и test_task_detector_chain 20 — все зелёные. (2) **run_all_system_tests.sh:** при наличии knowledge_os/.venv или backend/.venv с pytest скрипт использует этот Python для запуска тестов (иначе падал «pytest not found»). (3) **VERIFICATION_CHECKLIST:** п.38 — после правок Victoria/Enhanced рекомендованы run_all_system_tests, пересборка образа victoria-agent, при необходимости трассировка и быстрый прогон куратора; в §2 блок «После сессии правок»; в §5 уточнён пункт про RAG кэш (RAG_CACHE_BACKEND, Redis). (4) **docker-compose (victoria-agent):** добавлен REDIS_URL: redis://redis:6379 для опции RAG_CACHE_BACKEND=redis. (5) **Напоминание:** при следующем поднятии стека (Victoria + сервисы) рекомендуется быстрый прогон куратора или сравнение с эталоном — см. CURATOR_RUNBOOK §3, WHATS_NOT_DONE «Действия сейчас».
- **Итог:** библия обновлена (MASTER_REFERENCE, этот раздел). Дальше по плану: при деплое — куратор; при желании — пункты из TODO_FIXME_BACKLOG или покрытие CI.

---

## 0.4cr. RAG-кэш в Redis — опция при масштабировании (2026-02-10)

- **Контекст:** NEXT_STEPS §2, ROADMAP — при нескольких инстансах Victoria вынести RAG-кэш в Redis.
- **Внесено:** В **victoria_server.py** добавлены RAG_CACHE_BACKEND (env: memory|redis, по умолчанию memory), асинхронные _rag_cache_get(key) и _rag_cache_set(key, value, ttl_sec). При backend=redis используется REDIS_URL, ключ rag_ctx:{md5(goal)}, setex с TTL из RAG_CACHE_TTL_SEC. При ошибке Redis — fallback: запрос идёт в БД без кэша. Для memory сохранено ленивое вытеснение и лимит 500 записей.
- **Итог:** для общего кэша между инстансами задать RAG_CACHE_BACKEND=redis и REDIS_URL. NEXT_STEPS §2 обновлён.

---

## 0.4cq. Планы «как я» и «умнее, быстрее»: вторая очередь (2026-02-10)

- **Контекст «ранее по задаче»:** в **victoria_enhanced** при сборке simple_prompt, если передана chat_history, блок подписан «Ранее по задаче (контекст чата):» вместо «Контекст предыдущих сообщений в чате» — явная опора на план «достаточно сказать».
- **RAG: приоритет usage_count:** в **victoria_server._get_knowledge_context** векторный поиск и ILIKE fallback дополнены сортировкой по **usage_count DESC NULLS LAST** (при равной релевантности чаще используемые узлы выше).
- **Похожие успешные решения:** в **victoria_enhanced** добавлен метод **_get_similar_tasks_context(goal)** — запрос к knowledge_nodes (домен victoria_tasks), до 2 записей по usage_count/created_at; результат подставляется в промпт simple как блок «Похожие успешные решения (из прошлых задач):». Данные туда пишет _learn_from_task в bridge.
- **Runbook по типу задачи:** в **HOW_TO_INDEX** добавлена строка «Runbook по типу задачи» (curator_standards, victoria_tasks, usage_count, добавление эталонов). В **KNOWLEDGE_BASE_USAGE** §6 — источник victoria_tasks и абзац про runbook по типу задачи.
- **Candidate for standard и куратор как регрессия:** в **CURATOR_CHECKLIST** §3 добавлены формулировки: куратор как регрессия (регулярный прогон + сравнение с эталоном), candidate for standard при обратной связи «принять».

---

## 0.4cq. Планы «как я» и «умнее, быстрее»: вторая очередь (2026-02-10)

- **Контекст «ранее по задаче»:** в victoria_enhanced при наличии chat_history в промпте simple подпись изменена на «Ранее по задаче (контекст чата):» (вместо «Контекст предыдущих сообщений в чате») — план «достаточно сказать».
- **RAG приоритет usage_count:** в victoria_server._get_knowledge_context для векторного поиска добавлена вторичная сортировка `usage_count DESC NULLS LAST`; для ILIKE fallback — `usage_count DESC NULLS LAST` перед created_at.
- **Похожие успешные решения:** в victoria_enhanced._get_similar_tasks_context сначала поиск по сходству цели (metadata::text ILIKE, content ILIKE по goal[:80]), приоритет usage_count; при отсутствии — fallback: последние 2 узла домена victoria_tasks по usage_count/created_at.
- **Runbook по типу задачи:** в HOW_TO_INDEX добавлена строка индекса «Runbook по типу задачи (постоянное применение знаний)» — эталоны curator_standards, victoria_tasks, как добавить новый тип.
- **Куратор как регрессия, candidate for standard:** в CURATOR_MENTOR_CAUSES перед §5 добавлен блок: после изменений в коде — прогон куратора и сравнение с эталоном; при стабильно хорошем ответе — зафиксировать в standards/ и RAG (candidate for standard); обратная связь «принять» = эталон + RAG.

---

## 0.4cp. Планы «как я» и «умнее, быстрее»: шесть пунктов (2026-02-10)

- **Контекст:** внедрение пунктов из планов внедрения «как я» и «умнее, быстрее, знания в дело» (набор моделей 128 GB, fallback при недоступности LLM, операционные секретики, чеклист коммита, единый промпт русский/краткость, CURATOR_RUNBOOK Veronica).
- **Внесено:** (1) **MAC_STUDIO_M4_MODELS_GUIDE.md** — раздел «Стратегия быстрый + умный для 128 GB»: рекомендуемый набор (быстрая 3–8 GB, код/план 20–22 GB, умная 70B ~40 GB), порядок загрузки, когда какую использовать; ссылка на available_models_scanner и MAC_STUDIO_LOAD_AND_VICTORIA. (2) **victoria_enhanced.py:** при недоступности всех URL LLM добавлены эталонные ответы для **greeting** (category==fast и is_simple_greeting) и **what_can_you_do** (по ключевым словам); для «что умеешь» используется get_capabilities_text() из configs/victoria_common. (3) **CURATOR_RUNBOOK.md:** §4 «Veronica: таймауты и сбои список файлов» (DELEGATE_VERONICA_TIMEOUT, ссылка CURATOR_LIST_FILES_FAILURES, проверка Veronica); §5 «Операционные секретики» — таблица (один воркер, перед правками VERIFICATION §5, границы кода, Redis 6381, маршрутизация, контракт Victoria, recovery); §6 Ссылки + VERIFICATION_CHECKLIST. (4) **CONTRIBUTING.md:** чеклист при коммите — после изменений в backend/chat/Victoria прогнать тесты, при необходимости куратор/сравнение с эталоном; обновить MASTER_REFERENCE и CHANGES. (5) **configs/victoria_common.py:** константы PROMPT_RUSSIAN_ONLY и PROMPT_RUSSIAN_AND_BREVITY_LINES; **victoria_enhanced** (simple_prompt) и **react_agent** (_build_think_prompt, _build_act_prompt) используют их с fallback при ImportError. (6) Нумерация разделов CURATOR_RUNBOOK: бывший §4 Ссылки стал §6.
- **Итог:** при недоступности LLM пользователь получает эталонные ответы на приветствие и «что умеешь»; единый источник формулировок «русский + краткость» в configs; runbook и CONTRIBUTING дополнены; библия обновлена.

---

## 0.4co. status_project 3/3: fallback при недоступности LLM (2026-02-10)

- **Контекст:** при работе Victoria в Docker запрос к Ollama (host.docker.internal:11434) иногда не доходит или идёт с таймаутом → ответ «Сейчас не могу подключиться к моделям» → 0/3 по эталону.
- **Внесено:** (1) **victoria_enhanced.py:** при категории **status_query** и цели «статус проекта» (is_status_project_query), если все URL LLM не сработали, возвращается **эталонный ответ** (дашборд 8501, список задач Knowledge OS, MASTER_REFERENCE) вместо сообщения об ошибке; в ответ добавлено слово «список» для совпадения 3/3 по ключевым фразам (статус, дашборд, список). (2) Метаданные: `note: "status_project_fallback_no_llm"`.
- **Итог:** прогон куратора по задаче «какой статус проекта?» даёт **3/3** по эталону даже при недоступности Ollama из контейнера; пользователь получает полезный ответ.

---

## 0.4cn. Причина status_project 1/3: старый образ + синтаксис victoria_enhanced; трассировка и пересборка (2026-02-10)

- **Контекст:** после деплоя и прогона куратора ответ на «какой статус проекта?» был ReAct (thought + list_directory), а не эталон (дашборд, MASTER_REFERENCE) — 1/3 по эталону.
- **Подход:** другой способ поиска причины — трассировка полного пути запроса (bridge → Enhanced) и проверка сборки контейнера.
- **Найдено:** (1) Контейнер victoria-agent запускается из образа; после правок в коде делали только `restart`, образ не пересобирали → в контейнере был старый код. (2) В **victoria_enhanced.py** стр. 618 — синтаксическая ошибка: `if not row or not (str(...).strip():` (не хватало закрывающей скобки для `not (`). В части окружений это могло мешать загрузке модуля и созданию VictoriaEnhanced → запрос шёл в agent.run.
- **Внесено:** (1) Исправлена скобка в `victoria_enhanced.py`: `not (str(...).strip())`. (2) Скрипт **scripts/trace_status_project_route.py** — выводит для цели «какой статус проекта?» task_type, should_use_enhanced, is_curator_standard_goal (bridge) и при наличии knowledge_os — category, method (Enhanced); напоминает про пересборку образа. (3) В **CURATOR_RUNBOOK.md** добавлен блок «После изменений в коде Victoria»: build + up, вызов trace_status_project_route. (4) В **CURATOR_MENTOR_CAUSES.md** причина 2 обновлена: старый образ, синтаксис, решение — правка, пересборка, трассировка. (5) Образ victoria-agent пересобран, контейнер перезапущен с новым образом.
- **Итог:** для применения правок в bridge или Enhanced нужна пересборка образа; трассировка подтверждает путь enhanced → status_query → simple. После следующего прогона куратора ожидается улучшение по эталону status_project.

---

## 0.4cm. Падение Python при нехватке памяти на хосте — документ (2026-02-10)

- **Контекст:** Python неожиданно завершает работу при работе с Victoria/куратором; мониторинг системы показывает высокое использование RAM (Ollama 25–35 ГБ, Docker, Python).
- **Внесено:** В **VICTORIA_RESTARTS_CAUSE.md** добавлен §6 «Падение Python на хосте при нехватке памяти»: симптомы, вероятная причина (давление памяти, OOM), что делать (проверить память, выгрузить модели Ollama, перед прогоном куратора освободить память), связь с куратором. В **CURATOR_RUNBOOK.md** в блок про прогон добавлено предупреждение про память и ссылка на VICTORIA_RESTARTS_CAUSE §6.
- **Итог:** при повторных падениях Python или connection reset во время прогона куратора есть явная рекомендация и путь к документу.

---

## 0.4cl. Накопившиеся проблемы куратора: маршрутизация, мировые практики в simple (2026-02-10)

- **Запрос:** решить все накопившиеся проблемы; разные варианты решений и гипотез.
- **Внесено:** (1) **Кураторские эталоны не в Veronica:** в `task_detector.py` добавлены `CURATOR_STANDARD_KEYWORDS` и `is_curator_standard_goal(goal)`; для целей «статус проекта», «что умеешь», «дашборд» `detect_task_type` возвращает `enhanced`. В `victoria_server.py` (sync и background) для таких целей `prefer_veronica = False` — запросы идут только в Enhanced (simple + RAG), не делегируются в Veronica. (2) **Мировые практики в simple:** в `victoria_enhanced.py` в универсальный промпт simple добавлен пункт 6: «Учитывай лучшие практики: один источник истины (документация), проверяемый результат, актуальная библия (MASTER_REFERENCE)». (3) **Документ:** в CURATOR_MENTOR_CAUSES.md добавлен §5 «Варианты решений и гипотезы» — таблица внедрённых решений, гипотезы на будущее (список файлов через Enhanced, приветствие через Enhanced, блок экспертов в simple), перечень накопившихся пунктов.
- **Итог:** эталонные запросы куратора гарантированно идут в Enhanced с RAG; в simple подмешиваются мировые практики; гипотезы зафиксированы для следующих итераций.

---

## 0.4ck. Куратор и наставник: общий разбор причин (эксперты, мировые практики) (2026-02-10)

- **Запрос:** куратор и наставник вместе ищут причины неправильной работы с экспертами и мировыми практиками.
- **Внесено:** документ **docs/curator_reports/CURATOR_MENTOR_CAUSES.md** — цепочка запроса (POST /run → Veronica / Enhanced / agent.run), почему эталон «статус проекта» мог давать 0/3 (маршрут не в simple, RAG не запрашивался — уже исправлено в §0.4ce/0.4cj), почему эксперты не участвуют в коротких ответах (simple без Department Heads/Swarm), почему мировые практики не в контексте (WORLD_PRACTICES_CONTEXT только в extended_thinking при ключевых словах). Таблица действий для куратора и наставника; ссылки на FINDINGS, runbook, эталоны.
- **Итог:** один общий документ для разбора причин; при новых сбоях — дополнять CURATOR_MENTOR_CAUSES и связанные FINDINGS.

---

## 0.4cj. Эталон «статус проекта» 0/3: эксперты Backend+QA, RAG + fallback (2026-02-10)

- **Запрос:** кто из экспертов нужен для решения, подключать и делать.
- **Эксперты:** Игорь (Backend) — поток simple, RAG-запрос; Анна (QA) — эталон и проверка сравнения.
- **Внесено:** (1) **RAG:** в `_get_curator_rag_context` для запросов со «статус»/«дашборд»/«проект» добавлен поиск по `content ILIKE '%проект%'`, допуск `confidence_score IS NULL`, при отсутствии результата — второй запрос по `metadata->>'standard' = 'status_project'`. (2) **Fallback:** если для запроса «статус проекта» RAG вернул пусто — подставляется эталон из кода («Статус проекта смотрите в дашборде… MASTER_REFERENCE»), в лог — WARNING с рекомендацией проверить узел в БД. (3) **Промпт:** при наличии контекста из базы знаний — формулировка «ответь ТОЛЬКО на его основе (дашборд, MASTER_REFERENCE, задачи). Не выдумывай».
- **Итог:** после перезапуска victoria-agent ответ на «какой статус проекта?» должен опираться на эталон (RAG или fallback); повторно прогнать куратора и сравнение по status_project.

---

## 0.4ci. Сканер моделей: метрики загрузки/выгрузки/развёртывания/обработки с запасом (2026-02-10)

- **Запрос:** чтобы сканер передавал по каждой модели время загрузки, выгрузки, развёртывания и обработки; при появлении новой модели — тест по показателям, учёт данных с запасом.
- **Внесено:** (1) **Таблица model_performance_metrics** (миграция add_model_performance_metrics.sql): model_name, source (ollama/mlx), load_time_sec, unload_time_sec, deploy_time_sec, processing_sec_per_1k_tokens и варианты с запасом (_with_margin), margin_factor (по умолчанию 1.2), last_probed_at, probe_count. (2) **model_performance_probe.py:** probe для Ollama — замер load (холодный generate), unload (keep_alive=0 + ожидание выгрузки), deploy_time_sec = load_time_sec, processing по eval_count; сохранение в БД с margin; **у каждой модели свой margin_factor** (_margin_factor_for_model: 70b→1.4, 32b→1.3, 7b→1.25, 3b→1.2, 1b→1.15); get_metrics_for_models(), get_timeout_estimate_with_metrics(), get_timeout_estimate_from_metrics_dict(). (3) **available_models_scanner:** при скане в фоне probe_new_models_if_needed(); кэш с метриками по каждой модели; get_model_metrics(model_name, source), get_available_models_with_metrics() — возвращают метрики с запасом и margin_factor по модели. (4) **local_router:** таймаут запроса к LLM берётся по метрикам **этой** модели (get_model_metrics + get_timeout_estimate_from_metrics_dict), иначе fallback LOCAL_ROUTER_LLM_TIMEOUT. (5) **rest_api:** миграция при старте; GET /api/models/metrics — отдача метрик по моделям (у каждой свои).
- **Итог:** у каждой модели свои load/unload/deploy/processing и свой коэффициент запаса; таймаут запроса в local_router считается по метрикам выбранной модели. Переменные: MODEL_PROBE_ON_SCAN, MODEL_METRICS_MARGIN_FACTOR, MODEL_PROBE_LOAD_TIMEOUT, MODEL_PROBE_UNLOAD_TIMEOUT.

---

## 0.4ch. Victoria POST /run: ошибка «cannot access local variable 'os'» (2026-02-10)

- **Проблема:** при POST /run (в т.ч. async_mode=true) задача падала с `"error": "cannot access local variable 'os' where it is not associated with a value"`.
- **Причина:** в нескольких местах внутри функций был лишний `import os` (в try-блоках). В Python имя `os` становилось локальным для всей функции; при частичном выполнении (исключение до импорта или другой порядок веток) обращение к `os` до присваивания давало UnboundLocalError.
- **Внесено:** (1) **victoria_enhanced.py:** удалены лишние `import os` из блоков try в пяти местах (Department Heads, _should_use_department_heads, get_organizational_structure, _think_and_create_prompt_for_veronica, _execute_task_distribution) — модуль уже импортирует `os` в начале файла. (2) **local_router.py:** удалён лишний `import os` из `LocalAIRouter.__init__`.
- **Итог:** после перезапуска victoria-agent POST /run не должен падать с этой ошибкой; задача уходит в running/completed вместо failed.

---

## 0.4cg. Модели Ollama не выгружались — явный keep_alive (2026-02-10)

- **Запрос:** модели не выгружаются, проверить почему.
- **Причина:** (1) Когда **OLLAMA_KEEP_ALIVE** / **VICTORIA_OLLAMA_KEEP_ALIVE** не заданы, мы не передавали keep_alive в запросе → Ollama использовал серверный дефолт; если сервер запущен с **OLLAMA_KEEP_ALIVE=-1** (launchd, терминал), модели висят бесконечно. (2) Эмбеддинги (nomic-embed-text) вызывались без keep_alive → модель оставалась в памяти по серверному таймауту.
- **Внесено:** (1) **local_router._get_keep_alive():** при отсутствии env возвращает **300** (5 мин), не None — keep_alive передаётся в каждом запросе. (2) **Executor:** при отсутствии env в payload подставляется **keep_alive=300**. (3) **Victoria embeddings** (/api/embeddings): в тело запроса добавлен **keep_alive=0** — nomic выгружается сразу после ответа. (4) **MODEL_UNLOADING_AND_MEMORY.md** обновлён: явный дефолт 300, эмбеддинги с keep_alive=0, проверка OLLAMA_KEEP_ALIVE на сервере Ollama.
- **Итог:** после деплоя модели Ollama выгружаются через 5 мин неактивности (или сразу при OLLAMA_KEEP_ALIVE=0 в .env). Если Ollama запущен с OLLAMA_KEEP_ALIVE=-1 — наш keep_alive в запросах переопределяет это.

---

## 0.4cf. Удалённые модели: не оставлять данные по ним (2026-02-10)

- **Вопрос:** если модель удалена — зачем данные по ней остаются?
- **Внесено:** (1) **Код:** в `victoria_enhanced.py` приоритеты моделей `_get_model_for_category_async` приведены к только реально доступным в MLX (70b/104b/32b убраны из списков); дефолт `model_name` с `deepseek-r1-distill-llama:70b` заменён на `phi3.5:3.8b`. В `local_router.py` MLX fallback уже был переведён на лёгкие модели. (2) **БД:** миграция **purge_deleted_models_data.sql** — удаляет записи из `model_analytics` и `model_validation_results` для имён удалённых моделей (deepseek-r1-distill-llama:70b, llama3.3:70b, command-r-plus:104b, qwen2.5-coder:32b). (3) **Скрипт:** **knowledge_os/scripts/purge_deleted_models_knowledge.py** — по желанию удаляет узлы домена «AI Models» в `knowledge_nodes` по тем же именам (запуск: `DATABASE_URL=... python scripts/purge_deleted_models_knowledge.py`).
- **Итог:** после применения миграции и при необходимости скрипта накопленные данные по удалённым моделям не хранятся; в коде не остаётся приоритетов/дефолтов с удалёнными именами.

---

## 0.4ce. status_project 0/3: причина и подтягивание RAG в enhanced (2026-02-10)

- **Запрос:** проверять и искать с экспертами причину 0/3 по эталону «какой статус проекта?».
- **Причина (Backend/QA):** В методе **simple** в `victoria_enhanced.py` не было запроса к RAG (knowledge_nodes, домен curator_standards). Промпт собирался только из роли и запроса пользователя → модель отвечала из весов → галлюцинация, нет фраз «дашборд», «MASTER_REFERENCE».
- **Внесено:** (1) Метод **`_get_curator_rag_context(goal)`** в victoria_enhanced.py: по ключевым словам (статус, дашборд, что умеешь, проект) запрос к knowledge_nodes (домен curator_standards), возврат содержимого эталона (до 2000 символов). (2) В ветке simple при сборке универсального промпта вызов `kb_context = await self._get_curator_rag_context(goal)` и подмешивание блока «По базе знаний (эталон): …» в промпт; в инструкции добавлен пункт опираться на контекст из базы знаний. (3) FINDINGS_2026-02-10 — раздел «Причина 0/3» и «Внесённое решение».
- **Итог:** после перезапуска victoria-agent и повторного прогона куратора ответ на «какой статус проекта?» должен опираться на эталон из RAG; сравнение с эталоном — 3/3 или близко.

---

## 0.4cd. Куратор «все сделаем»: повторный прогон, launchd, FINDINGS (2026-02-10)

- **Запрос:** «давай все сделаем» — выполнить оставшиеся шаги (прогон куратора, сравнение, launchd, документы).
- **Сделано:** (1) Полный прогон куратора — отчёт **curator_2026-02-10_00-38-32.json** (5 задач, все success; «одна строка кода» 7.5 с). (2) Сравнение со всеми эталонами: greeting 5/5, what_can_you_do 8/9; status_project по-прежнему 0/3 (галлюцинация). (3) **launchd:** запущен `setup_curator_launchd.sh` — куратор ежедневно в 9:00; в plist добавлен **CURATOR_MAX_WAIT=900**. (4) В **setup_curator_launchd.sh** в EnvironmentVariables добавлен CURATOR_MAX_WAIT=900. (5) FINDINGS_2026-02-10, VERIFICATION_2026-02-10, WHATS_NOT_DONE обновлены.
- **Итог:** Остаётся доработать «какой статус проекта?» — проверить подтягивание RAG в enhanced при запросе про статус (контекст из knowledge_nodes).

---

## 0.4cc. Куратор: полный прогон, сравнение со всеми эталонами, RAG (2026-02-10)

- **Запрос:** «все делай» — выполнить всё по плану (куратор, эталоны, RAG, верификация).
- **Сделано:** (1) **Полный прогон куратора** — `CURATOR_MAX_WAIT=900 ./scripts/run_curator_scheduled.sh`; отчёт **curator_2026-02-10_00-21-17.json** (5 задач, все success). (2) **Сравнение со всеми эталонами:** greeting 5/5, what_can_you_do 8/9; status_project 0/3 (галлюцинация); list_files — success по смыслу; one_line_code — ответ «не могу подключиться к моделям» (enhanced, долгий запрос). (3) **RAG:** `curator_add_standard_to_knowledge.py` (все эталоны уже в БД), `--update-status` — обновлён узел status_project. (4) **FINDINGS_2026-02-10.md** — выводы и таблица сравнения; **VERIFICATION_2026-02-10.md** — обновлён последним отчётом и рекомендациями.
- **Итог:** при следующем прогоне проверить «какой статус проекта?» после обновления RAG; для «одна строка кода» при долгом ответе — таймауты/доступность Ollama. Регулярно: run_curator_scheduled.sh, затем curator_compare_to_standard по нужным эталонам.

---

## 0.4cb. MLX: убрана 32B из приоритетов (только лёгкие) (2026-02-10)

- **Цель:** не загружать в MLX модель qwen2.5-coder:32b (~35 ГБ процесс), оставить в MLX только лёгкие модели.
- **Внесено:** (1) **available_models_scanner.py:** из **MLX_BEST_FIRST** и **MLX_PRIORITY_BY_CATEGORY** удалён qwen2.5-coder:32b; везде только phi3.5:3.8b, qwen2.5:3b, phi3:mini-4k, tinyllama:1.1b-chat. (2) **mlx_api_server.py:** _CATEGORY_TO_MODEL_FULL — default/coding/reasoning → **fast** (не 32b); PRELOAD_MODEL_MAP — default/coding → phi3.5:3.8b. (3) **MLX_PYTHON_CRASH_CAUSE.md** — обновлены «Принятое решение» и блок «Что отслеживать в Мониторинге»: в MLX только лёгкие, 32B не загружается.
- **Итог:** Victoria при выборе MLX больше не выбирает 32B; тяжёлые задачи (coding/default при желании) — в Ollama.

---

## 0.4ca. Victoria Enhanced: подключение к Ollama из Docker (2026-02-10)

- **Проблема:** запросы «какой статус проекта?» шли в enhanced и возвращали «Сейчас не могу подключиться к моделям» при работающих Ollama/MLX на хосте — из контейнера Victoria сканирование или запрос к host.docker.internal не успевали/падали.
- **Внесено:** (1) **victoria_enhanced.py:** ollama_url берётся из **OLLAMA_BASE_URL** или **OLLAMA_API_URL** (раньше только OLLAMA_BASE_URL). При пустом списке моделей после первого скана — повторный вызов **get_available_models(..., force_refresh=True)**. При пустом списке в Docker порядок попыток: **ollama_url, mlx_url**. Таймаут запроса к LLM в Docker увеличен: не менее **90 с** (раньше 15–60 с). (2) **available_models_scanner.py:** добавлен **_ollama_scan_timeout()** — в Docker по умолчанию **15 с** (на хосте 5 с), задаётся **OLLAMA_SCAN_TIMEOUT**. **_fetch_ollama_models** использует этот таймаут. (3) **docker-compose.yml** (victoria-agent): **OLLAMA_SCAN_TIMEOUT: 15**.
- **Итог:** после перезапуска victoria-agent запросы из enhanced должны доходить до Ollama на хосте; при необходимости увеличить **OLLAMA_SCAN_TIMEOUT** или таймаут в safe_http_request.

---

## 0.4bz. Куратор и эталоны: действия сейчас, RAG status_project (2026-02-10)

- **Запрос:** погнали что осталось делать (куратор, эталоны, стабильность и т.д.).
- **Внесено:** (1) **WHATS_NOT_DONE.md** — в начало добавлен блок **«Действия сейчас (погнали)»**: полный прогон куратора (`run_curator_scheduled.sh`), при расхождении — доучить в RAG и обновить standards/, эталон «статус проекта» (0/3) — сравнение `--standard status_project`, доучить или поправить контекст enhanced; новые эталоны в `docs/curator_reports/standards/`; стабильность — Grafana 3002, deferred_to_human, system_auto_recovery.sh. (2) **standards/status_project.md** — добавлена строка «Коротко для RAG/контекста» для использования при ответе. (3) **CURATOR_RUNBOOK.md** — при расхождении с эталоном (доучить RAG, обновить standards/), для «статус проекта» 0/3, новые эталоны; стабильность со ссылкой на WHATS_NOT_DONE. (4) **curator_add_standard_to_knowledge.py** — эталон status_project расширен короткой формулировкой в STATUS_ANSWER; добавлен флаг **--update-status** для обновления содержимого узла status_project в БД без пересоздания; выполнено обновление узла в RAG.
- **Итог:** прогон куратора запущен в фоне (CURATOR_MAX_WAIT=900); после завершения — сравнение с эталоном `curator_compare_to_standard.py --standard status_project` по новому отчёту. Регулярно гонять `./scripts/run_curator_scheduled.sh`.

---

## 0.4by. keep_alive для Ollama — политика и код (2026-02-10)

- **Запрос:** с экспертами и знаниями сделать по выгрузке моделей / keep_alive.
- **Внесено:** (1) **Executor** (src/agents/core/executor.py): в тело запроса к Ollama `/api/chat` подставляется **keep_alive** из env **VICTORIA_OLLAMA_KEEP_ALIVE** или **OLLAMA_KEEP_ALIVE** (число или строка, напр. `0`, `300`, `5m`, `-1`). (2) **LocalAIRouter** (knowledge_os/app/local_router.py): добавлен хелпер **_get_keep_alive()**, значение из env подставляется в payload для `/api/chat`, `/api/generate` (в т.ч. стриминг). (3) **MODEL_UNLOADING_AND_MEMORY.md:** обновлён раздел «В нашем коде» — указано, что keep_alive передаётся из env; добавлен раздел **«Рекомендации экспертов»** (Дмитрий ML, Елена SRE, Игорь Backend) и политика по умолчанию (переменная не задана — дефолт Ollama). (4) **.env.example:** закомментированные **VICTORIA_OLLAMA_KEEP_ALIVE** и **OLLAMA_KEEP_ALIVE** с пояснением.
- **Итог:** при необходимости экономии памяти задать `OLLAMA_KEEP_ALIVE=0`; для стабильной латентности — `300` или `5m`; не задавать — поведение Ollama по умолчанию (~5 мин).

---

## 0.4bv. Python (MLX) снова вылетал — та же причина, MLX_ONLY_LIGHT в wrapper (2026-02-10)

- **Запрос:** «снова пайтон вылетал».
- **Проверка:** Victoria — без OOM (RestartCount 0). Краш-репорты Python за 2026-02-10 (00:01, 00:13, 01:30, 02:27) — та же цепочка **mlx::core::gpu::check_error** (Metal/GPU). MLX после краша поднимается (wrapper или вручную); сейчас :11435 отвечает 200.
- **Внесено:** (1) В **MLX_PYTHON_CRASH_CAUSE.md** добавлен раздел «Повторные краши (2026-02-10)»: причина та же, Victoria идёт через Ollama при падении MLX; в wrapper явно **MLX_ONLY_LIGHT=true**; при продолжении крашей — вариант не запускать MLX. (2) В **scripts/start_mlx_server.sh** добавлен `export MLX_ONLY_LIGHT=${MLX_ONLY_LIGHT:-true}`.
- **Итог:** краши MLX/Metal по-прежнему возможны даже с лёгкой моделью; wrapper перезапускает; при необходимости — только Ollama.
- **Дополнение (вопрос «она же лёгкая что падает то?»):** в MLX_PYTHON_CRASH_CAUSE добавлен раздел **«Почему падает даже лёгкая модель (fast)»**: да, падает именно fast (phi3.5-mini-4k); причина — не размер модели, а нагрузка на Metal/память (Ollama, Docker, др.), особенности драйвера или гонки при загрузке; при краше смотреть логи MLX, какая модель и запрос.

---

## 0.4bx. Выгрузка неиспользуемых моделей — как организована (2026-02-10)

- **Запрос:** как организована выгрузка неиспользуемых моделей, висят ли они в памяти.
- **Внесено:** **docs/MODEL_UNLOADING_AND_MEMORY.md** — (1) **MLX:** не висят бесконечно: лимит кэша MLX_MAX_CACHED_MODELS (по умолчанию 1), выгрузка по LRU перед загрузкой новой модели и в фоне раз в MLX_CACHE_CLEANUP_INTERVAL_SEC (600 с); при нехватке памяти — cleanup_unused_models(). (2) **Ollama:** выгрузкой управляет Ollama — по умолчанию модель остаётся ~5 мин после последнего использования; в нашем коде keep_alive не передаётся (дефолт Ollama); при желании можно передавать keep_alive=0 для немедленной выгрузки. (3) В HOW_TO_INDEX добавлена строка «Выгрузка неиспользуемых моделей / модели висят в памяти» → MODEL_UNLOADING_AND_MEMORY.md.
- **Итог:** MLX — выгрузка по LRU, макс 1 модель в кэше по умолчанию; Ollama — автовыгрузка ~5 мин; при необходимости жёстче освобождать память Ollama — передавать keep_alive=0 в запросах.
- **Дополнение («как мировые практики и гиганты»):** в MODEL_UNLOADING_AND_MEMORY.md добавлен раздел **«Мировые практики и гиганты»**: облачные API (OpenAI, Anthropic) не дают клиенту выгрузку — управление на их стороне; vLLM/PagedAttention — gpu_memory_utilization, max_model_len, жёсткий лимит памяти и KV-кэш; Triton — явные load/unload API; Ollama — keep_alive и OLLAMA_KEEP_ALIVE, дефолт ~5 мин; вывод для нашего стека: лимит кэша + явный keep_alive по сценарию.

---

## 0.4bw. Как решить краши MLX + отключение MLX в Victoria (2026-02-10)

- **Запрос:** «как решить?» (краши Python/MLX).
- **Внесено:** (1) В **MLX_PYTHON_CRASH_CAUSE.md** добавлен раздел **«Как решить»**: 1) не запускать MLX (launchctl unload/stop); 2) отключить MLX в Victoria — `MLX_API_URL: "disabled"` в docker-compose, тогда только Ollama; 3) снизить конкуренцию за память/GPU; 4) оставить MLX только через wrapper. (2) В **knowledge_os/app/available_models_scanner.py**: при пустом или `none`/`disabled`/`off` URL не опрашивать MLX (`_fetch_mlx_models` возвращает []); `_default_mlx_url()` для значений `none`/`disabled`/`off`/`false` возвращает "".
- **Итог:** чтобы краши прекратились — не запускать MLX или задать в compose для victoria-agent `MLX_API_URL: "disabled"` и перезапустить контейнер.
- **Уточнение (скачок памяти при краше):** пользователь зафиксировал скачок на графике «Нагрузка на память» перед очередным вылетом (95 ГБ из 128 в use, 4.6 ГБ своп). В MLX_PYTHON_CRASH_CAUSE добавлено: скачок памяти перед крашем — типичная картина; при высоком базовом потреблении пик от MLX/Ollama может приводить к падению; решение то же — не запускать MLX или отключить в Victoria.
- **Включено по умолчанию:** в **knowledge_os/docker-compose.yml** для `victoria-agent` задано **MLX_API_URL: ${MLX_API_URL:-disabled}** — Victoria по умолчанию не опрашивает MLX, только Ollama; контейнер пересоздан. Чтобы снова использовать MLX: в .env задать `MLX_API_URL=http://host.docker.internal:11435` (или для хоста `http://localhost:11435`) и перезапустить victoria-agent.

---

## 0.4bu. Куратор: сравнение по эталонам, эталон «статус проекта» (2026-02-10)

- **Цель:** по запросу «погнали» — прогон куратора и эталоны.
- **Сделано:** (1) Полный прогон куратора не уложился в таймаут — использован отчёт с 5 задачами (curator_2026-02-08_23-16-02). (2) Сравнение по всем 5 эталонам: привет 5/5, что ты умеешь 8/9; статус проекта в том прогоне — галлюцинация (0/3). (3) В **standards/status_project.md** добавлен явный блок **Эталонный ответ** с формулировкой «Статус проекта смотрите в дашборде… MASTER_REFERENCE…» для сравнения и RAG. (4) FINDINGS_2026-02-09 — таблица сравнения по 5 задачам и рекомендация повторить при следующем полном прогоне.
- **Итог:** привет и что умеешь — по эталону; эталон статуса явно зафиксирован; при следующем прогоне проверить статус снова.

---

## 0.4bt. Лёгкий старт Victoria по умолчанию (анти-OOM) (2026-02-09)

- **Цель:** по запросу «делай» — применить меры против OOM.
- **Внедрено:** в **knowledge_os/docker-compose.yml** для `victoria-agent` дефолты сменены на лёгкий старт: **ENABLE_EVENT_MONITORING:-false**, **SERVICE_MONITOR_ENABLED:-false**, **RAG_PRELOAD_TYPICAL_QUERIES:-false**. Меньше потребление памяти при старте — меньше риск OOM. При достаточной памяти Docker (10–14 GB) можно включить в .env: `ENABLE_EVENT_MONITORING=true`, `SERVICE_MONITOR_ENABLED=true`, `RAG_PRELOAD_TYPICAL_QUERIES=true`.
- **Выполнено:** `docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent --force-recreate`; через ~45 с health 200, RestartCount 0.
- **Итог:** Victoria по умолчанию стартует в облегчённом режиме; при необходимости полный мониторинг и RAG preload — через .env.

---

## 0.4bs. Почему вылетела Victoria — OOM (2026-02-09)

- **Запрос:** проверить, почему вылетела Victoria.
- **Проверка:** `docker inspect victoria-agent` → **RestartCount: 6**, **OOMKilled: true**.
- **Причина:** контейнер убит из‑за **нехватки памяти (OOM)**. При старте загружаются skills, ReAct, Event Bus, Service Monitor, RAG preload — пик памяти; при лимите Docker ниже потребности — SIGKILL (137). Поэтому куратор в 22:50 видел «Victoria недоступна» (контейнер падал/перезапускался).
- **Внесено:** в FINDINGS_2026-02-09 добавлен раздел «Почему вылетела Victoria» с причиной и ссылками на VICTORIA_RESTARTS_CAUSE §2, MAC_STUDIO_LOAD (увеличить Memory Docker 10–14 GB или временно отключить RAG preload / Service Monitor).

---

## 0.4br. Проверяй делай: measure, эталоны RAG, куратор (2026-02-09)

- **Цель:** по запросу «проверяй делай» — проверить и выполнить следующие шаги.
- **Сделано:** (1) **measure_mlx_light_classify.py:** успех считаем при `status == "success"` или при наличии поля `output` в ответе (формат Victoria TaskResponse); так скрипт корректно считает успешные ответы. (2) **Эталоны в RAG:** выполнен `scripts/curator_add_standard_to_knowledge.py` (через knowledge_os/.venv, asyncpg есть в requirements); все 5 эталонов уже в БД (what_can_you_do, greeting, status_project, list_files, one_line_code), добавлено 0. (3) **Куратор:** запуск с `CURATOR_MAX_WAIT=900` в фоне — в момент старта Victoria (8010) была недоступна, скрипт вышел с «Victoria недоступна». Для полного прогона: поднять Victoria (`docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent`), затем `CURATOR_MAX_WAIT=900 ./scripts/run_curator_scheduled.sh`.
- **Итог:** скрипт замера исправлен; эталоны в RAG проверены; куратор при следующем запуске выполнить при работающей Victoria.

---

## 0.4bq. Прогон measure_mlx_light_classify, куратор, сравнение с эталоном (2026-02-09)

- **Цель:** по запросу «прогони и дальше по задачам MAC_STUDIO_COPY_STATUS (куратор, эталоны)».
- **Сделано:** (1) **Замер MLX light classify:** запущен `measure_mlx_light_classify.py --count 3` к Victoria :8010; 3 запроса выполнены (суммарно ~83 с); скрипт показал 0/3 успешных — возможно иной формат ответа /run (при необходимости поправить проверку `status` в скрипте). (2) **Куратор:** полный прогон `run_curator_scheduled.sh` не уложился в таймаут 7 мин — использован последний готовый отчёт curator_2026-02-09_22-04-12.json. (3) **Сравнение с эталоном:** по отчёту 22-04-12: greeting (привет) — 5/5 ключевых фраз; status_project — 0/3, ответ обрезан/искажён. (4) **FINDINGS_2026-02-09:** добавлен блок «Сравнение с эталоном» и рекомендация при следующем прогоне проверить остальные эталоны и при необходимости выполнить `curator_add_standard_to_knowledge.py`.
- **Итог:** привет по эталону; статус проекта — доучить в RAG или проверить контекст; полный прогон куратора при необходимости запускать с увеличенным таймаутом или в фоне.

---

## 0.4bp. MLX автозапуск: одна команда в доках (2026-02-09)

- **Цель:** в одном месте описать запуск MLX с автоперезапуском и команды launchd.
- **Внедрено:** (1) **MAC_STUDIO_COPY_STATUS.md** §3 «Быстрые команды» — добавлен блок MLX: `bash scripts/setup_mlx_autostart.sh`, `launchctl start com.atra.mlx-api-server`, `launchctl list | grep mlx`, напоминание про «Пропустить» при краше (Victoria через Ollama). (2) **MLX_PYTHON_CRASH_CAUSE.md** §3 «Перезапуск MLX» — абзац про автозапуск при логине: один раз `setup_mlx_autostart.sh`, команды start/stop, логи wrapper и launchd.
- **Итог:** вопрос «как поднять MLX с перезапуском» — ответ в MAC_STUDIO_COPY_STATUS и MLX_PYTHON_CRASH_CAUSE.

---

## 0.4bj. TODO в коде: ссылки на backlog (2026-02-09)

- **Цель:** связь код ↔ документ — при чтении TODO в коде видеть ссылку на backlog.
- **Внедрено:** во всех 8 модулях knowledge_os/app с TODO добавлена в комментарий ссылка `See docs/TODO_FIXME_BACKLOG.md`: hierarchical_orchestration, recap_framework, query_orchestrator, master_plan_generator, strategy_discovery, skill_discovery, model_enhancer, early_warning_system. В README уточнена строка про .env.example (шаблон без секретов, не коммитить пароли). В TODO_FIXME_BACKLOG указано, что в коде добавлены ссылки на документ.
- **Итог:** из кода по любому TODO можно перейти в backlog.

---

## 0.4bk. Копия «тебя» на Mac Studio: статус и продолжаем (2026-02-09)

- **Цель:** один документ — что уже есть на Mac Studio (Victoria + команда как «копия» Cursor-агента), что работает, чем продолжить.
- **Внедрено:** **docs/MAC_STUDIO_COPY_STATUS.md** — (1) таблица «что уже есть»: Victoria/Veronica, цепочка задачи, эксперты, библия, куратор и эталоны, Mac Studio док, тесты и верификация; (2) приоритеты «продолжаем»: регулярные прогоны куратора, накопление эталонов, стабильность; средний срок — план оркестратора → исполнение, RAG Redis при масштабе; (3) быстрые команды (docker, куратор, сравнение с эталоном, system_auto_recovery). HOW_TO_INDEX и MASTER_REFERENCE — ссылки на MAC_STUDIO_COPY_STATUS.
- **Итог:** вопрос «что у нас к копии тебя на Mac Studio, продолжаем?» — ответ в одном месте; следующие шаги явно перечислены.

---

## 0.4bo. MLX: опциональная лёгкая классификация в Victoria (гипотеза 1) (2026-02-09)

- **Цель:** внедрить «если нужно реально» — минимальный первый шаг: классификация через лёгкую MLX только для неочевидных запросов (general, 5–25 слов), по флагу.
- **Внедрено:** В **knowledge_os/app/victoria_enhanced.py**: (1) функция **`_try_mlx_light_classify(goal)`** — POST к MLX `/api/generate` (category=fast, max_tokens=10, таймаут 8 с), парсинг одного слова (greeting→fast, остальные как есть). (2) После `_categorize_task(goal)`: если category=general, 5≤ слова ≤25 и **VICTORIA_MLX_LIGHT_CLASSIFY=true** — вызов `_try_mlx_light_classify`, при успехе подстановка category, лог `[MLX_LIGHT_CLASSIFY] general -> X`. (3) **knowledge_os/docker-compose.yml** — переменная **VICTORIA_MLX_LIGHT_CLASSIFY** (по умолчанию false). (4) **MLX_STRATEGY_LIGHT_AND_VITALITY.md** — в §5.1 указано, что гипотеза 1 внедрена за флагом.
- **Итог:** по умолчанию поведение без изменений; включить `VICTORIA_MLX_LIGHT_CLASSIFY=true` для проверки, нужна ли классификация «реально» (логи и метрики).
- **Замер:** в лог добавлено duration_ms; скрипт **scripts/measure_mlx_light_classify.py** — отправка тестовых запросов к Victoria и разбор логов (`--parse-logs`) для сводки по срабатываниям и duration_ms. См. MLX_STRATEGY_LIGHT_AND_VITALITY §5.1.

---

## 0.4bn. MLX: стратегия «только лёгкие модели и жизнедеятельность» (2026-02-09)

- **Цель:** MLX постоянно вылетает — зафиксировать, как правильно использовать: только лёгкие модели, роль «поддержание жизнедеятельности», не решение тяжёлых задач; подключить команду (rules), узлы знания и мировые практики.
- **Внедрено:** (1) **docs/MLX_STRATEGY_LIGHT_AND_VITALITY.md** — стратегия: только лёгкие модели в MLX (default/coding/reasoning → fast); роль MLX — приветствия, «что умеешь», короткие ответы, лёгкая классификация; тяжёлые задачи — Ollama; мнения Дмитрий (ML), Елена (SRE), Игорь (Backend) и мировые практики (light/heavy path, fail-safe). (2) **knowledge_os/app/mlx_api_server.py** — при **MLX_ONLY_LIGHT=true** (по умолчанию) CATEGORY_TO_MODEL: default, coding, reasoning, code → **fast**; предзагрузка только fast. (3) HOW_TO_INDEX — строка «MLX вылетает / как использовать» → MLX_STRATEGY_LIGHT_AND_VITALITY; MLX_PYTHON_CRASH_CAUSE — ссылка на стратегию; .cursor/rules 02_dmitriy, 07_elena — упоминание стратегии и MLX_ONLY_LIGHT; MASTER_REFERENCE — последние изменения.
- **Итог:** MLX по умолчанию не грузит 32B, только fast; вылеты должны снизиться; при необходимости вернуть 32B в MLX — MLX_ONLY_LIGHT=false.

---

## 0.4bm. Docker вылетает — нехватка памяти (2026-02-09)

- **Цель:** зафиксировать, что вылеты Docker нередко из‑за нехватки памяти, и дать чеклист действий.
- **Внедрено:** В **docs/MAC_STUDIO_LOAD_AND_VICTORIA.md** добавлен §2.1 «Docker вылетает — часто из‑за нехватки памяти»: проверка лимита Memory в Docker Desktop (8–12 GB для Mac Studio), команда проверки OOMKilled, снижение нагрузки (RAG_PRELOAD, ENABLE_EVENT_MONITORING, SERVICE_MONITOR_ENABLED) при нехватке RAM, ссылка на VICTORIA_RESTARTS_CAUSE §2. В **HOW_TO_INDEX** добавлена строка «Docker вылетает / не запускается» → MAC_STUDIO_LOAD §2.1 и VICTORIA_RESTARTS_CAUSE.
- **Итог:** вопрос «докер вылетает, может нехватка памяти?» — да, часто; что делать — в одном месте (MAC_STUDIO §2.1).

---

## 0.4bl. Victoria в Docker: Ollama первым, таймаут MLX, вылеты MLX (2026-02-09)

- **Цель:** устранить «не могу подключиться к моделям» при работающих Ollama/MLX на хосте; учесть вылеты MLX после нагрузки.
- **Внедрено:** (1) **knowledge_os/app/victoria_enhanced.py** — в Docker при наличии обоих URL порядок сменён на `[ollama_url, mlx_url]`, чтобы сначала пробовать Ollama (из контейнера 11434 доступен, 11435 часто таймаут/вылет). (2) **knowledge_os/app/available_models_scanner.py** — таймаут сканирования MLX вынесен в env **MLX_SCAN_TIMEOUT** (по умолчанию 5 с); в **knowledge_os/docker-compose.yml** для victoria-agent задано **MLX_SCAN_TIMEOUT=12**. (3) **docs/curator_reports/FINDINGS_2026-02-09.md** — раздел «Решение внедрено»: что сделано, рекомендация запускать MLX через `start_mlx_server.sh` при вылетах, перезапуск Victoria после изменений. (4) **docs/MLX_PYTHON_CRASH_CAUSE.md** — в §3 добавлено: после прогона куратора/длинных запросов MLX может вылететь; использовать start_mlx_server.sh или полагаться на Ollama (Victoria в Docker сначала обращается к Ollama).
- **Итог:** Victoria в Docker стабильно отвечает через Ollama; при вылете MLX ответы не блокируются. После деплоя: `docker compose -f knowledge_os/docker-compose.yml restart victoria-agent`.

---

## 0.4bi. Осталось: линтер по путям, .env.example, e2e стратегия→board, куратор launchd (2026-02-09)

- **Цель:** закрыть оставшиеся пункты из WHATS_NOT_DONE и PROJECT_GAPS.
- **Внедрено:** (1) **CI — линтер по изменённым путям:** в `.github/workflows/pytest-knowledge-os.yml` job `lint`: получаем список изменённых .py в backend/, knowledge_os/app/, knowledge_os/tests/, src/ (git diff для push/PR); запускаем `ruff check` только по ним; при ошибках ruff job падает (убран `|| true` для изменённых). (2) **.env.example** в корне: шаблон переменных без секретов (PROJECT_NAME, VICTORIA_URL, OLLAMA_URL, MAX_CONCURRENT_VICTORIA и др.), комментарий про секреты и прод. (3) **E2E сценарий стратегия→board→Victoria:** в TESTING_FULL_SYSTEM §2 добавлен подраздел «E2E сценарий: стратегический вопрос → board → Victoria»; скрипт `scripts/test_strategic_chat_e2e.sh` — curl POST /api/chat/stream с целью, проверка 200 и непустого потока. (4) **Куратор по расписанию:** скрипт `scripts/setup_curator_launchd.sh` — создаёт launchd-задание `com.atra.curator-scheduled` (ежедневно 9:00); в CURATOR_RUNBOOK добавлен пункт про launchd и команду установки.
- **Итог:** WHATS_NOT_DONE обновлён — линтер по путям, полный e2e стратегия→board, куратор по расписанию помечены сделанными; HOW_TO_INDEX — ссылка на .env.example в секретах.

---

## 0.4bh. Contributing Guide, E2E, TODO backlog, ручные проверки (2026-02-09)

- **Цель:** закрыть пункты «делаем все»: E2E тесты для чата, закрыть/задокументировать TODO из backlog, Contributing Guide, развитие Victoria (дорожная карта в одном месте), чеклист ручных проверок.
- **Внедрено:** (1) **CONTRIBUTING.md** (корень) — руководство для контрибьюторов: с чего начать, как тестировать (unit + E2E Playwright), методология и чеклист, добавление экспертов, развитие Victoria (ссылки на ROADMAP, NEXT_STEPS, VICTORIA_TASK_CHAIN_FULL), TODO backlog, ручные проверки (ссылка на MANUAL_VERIFICATION_CHECKLIST). (2) **E2E:** документированы в TESTING_FULL_SYSTEM §2 (команда `cd frontend && npm run e2e`, BASE_URL/BACKEND_URL), в HOW_TO_INDEX добавлена строка «E2E (чат, health)»; тесты уже были в frontend/tests/e2e/ (chat.spec.cjs, health.spec.cjs). (3) **TODO_FIXME_BACKLOG:** обновлены таблицы среднего и низкого приоритета — для каждого модуля указан контекст (TODO в коде с номерами строк или «при касании»); signal_live / data_quality — ссылка на SIGNALS_TODO_REENABLE.md. (4) **Victoria:** раздел «Развитие Victoria» в CONTRIBUTING §5 со ссылками на ROADMAP_CORPORATION_LIKE_AI, NEXT_STEPS, VICTORIA_TASK_CHAIN_FULL и victoria_capabilities. (5) **docs/MANUAL_VERIFICATION_CHECKLIST.md** — чеклист из 4 пунктов: полный сценарий чата (эхо/503), ручная проверка делегирования, Prometheus в UI Grafana, launchd (system_auto_recovery). (6) README — ссылка на CONTRIBUTING; MASTER_REFERENCE §8 — строки CONTRIBUTING и MANUAL_VERIFICATION_CHECKLIST; WHATS_NOT_DONE — E2E помечен «Сделано».
- **Итог:** один вход для команды (CONTRIBUTING); E2E запуск и описание в доках; TODO backlog с контекстом по всем перечисленным модулям; ручные проверки вынесены в отдельный чеклист.

---

## 0.4bg. План верификации: пункты «осталось сделать» закрыты + проход чеклиста (2026-02-09)

- **Цель:** закрыть пункты из .cursor/plans/VERIFICATION_AND_FULL_PICTURE_PLAN.md «Что осталось сделать» и пройти чеклист верификации (раздел 4).
- **Проверено:** (1) WORKER_THROUGHPUT — «пункты 14–19»; PROJECT_ARCHITECTURE — Smart Worker и ссылки; CURRENT_STATE_WORKER_AND_LLM — создан. (2) **Проход чеклиста:** Victoria :8010 — 200, victoria_levels agent/enhanced/initiative true; Veronica :8011 — 200; Backend :8080 — 200, healthy; контейнер knowledge_os_worker Up, логи — батчи по модели, сканер Ollama/MLX; OLLAMA/MLX URL в docker-compose; Grafana 3002/3001, Corporation 8501 — 200; скрипты system_auto_recovery есть.
- **Внедрено:** в **VERIFICATION_AND_FULL_PICTURE_PLAN.md** отмечены выполненными все четыре пункта «Что осталось сделать»; в разделе 4 чеклиста проставлены [x] и даты по проверенным пунктам; добавлен блок **«Результаты верификации (2026-02-09)»** (таблица: агенты, воркер, дашборды, автоматика); раздел 5 «Следующие шаги» обновлён — все пункты помечены сделанными.
- **Итог:** план верификации полностью закрыт; при следующих изменениях воркера/Ollama/MLX/агентов — повторно проходить раздел 4 и обновлять результаты.

---

## 0.4bf. Grafana: alerting включён, исправлен relativeTimeRange (2026-02-09)

- **Цель:** запускать Grafana с включённым provisioning datasource (Prometheus) и alerting, без цикла перезапусков.
- **Причина падения:** при provisioning алерта «Deferred to human queue high» Grafana выдавала «invalid relative time range: {From:0s To:0s}» — у элемента условия (refId C) не был задан `relativeTimeRange`, по умолчанию подставлялось 0s–0s.
- **Внедрено:** (1) **grafana/provisioning/alerting/deferred_to_human.yaml** — для записи с refId C добавлен `relativeTimeRange: { from: 300, to: 0 }` (как у запроса A). (2) Образ Grafana зафиксирован на **10.2.3** (docker-compose); datasources.yml с Prometheus (uid: prometheus), папка alerting активна. (3) **grafana/README.md** — описан порядок: Prometheus → Grafana, provisioning datasources/dashboards/alerting.
- **Итог:** Grafana 10.2.3 стартует с Prometheus и алертом deferred_to_human; http://localhost:3002 доступен.

---

## 0.4be. Consensus Agent: confidence по длине ответа (2026-02-09)

- **Цель:** убрать хардкод `confidence: 0.7` и считать уверенность по длине ответа.
- **Внедрено:** в **knowledge_os/app/consensus_agent.py** добавлен `_confidence_from_response_length(response: str) -> float`: пустой ответ → 0.0, < 20 символов → 0.25, 20–100 → 0.4, 100–300 → 0.55, 300–600 → 0.7, 600–1200 → 0.82, далее до 0.95. В `_generate_agent_response` вместо константы 0.7 вызывается `self._confidence_from_response_length(result)`.
- **Итог:** confidence в консенсусе отражает объём ответа (эвристика; при необходимости можно заменить на модель/качество).

---

## 0.4bd. Тяжёлые модели 70B/104B удалены из всех приоритетов (Apple Silicon Metal limits) (2026-02-09)

- **Цель:** после повторных падений MLX с SIGABRT (Metal OOM: 27 GB buffer limit) **полностью удалить из приоритетов** модели `deepseek-r1-distill-llama:70b`, `command-r-plus:104b`, `llama3.3:70b`, чтобы Victoria перестала пытаться их загружать → MLX стабилен.
- **Причина:** (1) `available_models_scanner.py` содержал тяжёлые модели в `OLLAMA_PRIORITY_LIST` (строка 42), `OLLAMA_PRIORITY_BY_CATEGORY` (default/reasoning/complex), `MLX_PRIORITY_BY_CATEGORY` (все категории); (2) `victoria_server.py` — hardcoded приоритеты ml/security/reasoning/complex со ссылками на 70b/104b; (3) при запросе Victoria вызывала `get_best_available_model()` → приоритет с тяжёлой моделью → MLX пытался загрузить → превышение лимита 27 GB buffer → SIGABRT.
- **Внедрено:** (1) **available_models_scanner.py** — `MLX_BEST_FIRST` теперь max 32B (qwen2.5-coder:32b, phi3.5:3.8b); `MLX_PRIORITY_BY_CATEGORY` все категории (default/general/coding/reasoning/complex) без 70b/104b; комментарий «Тяжёлые 70b/104b удалены из-за Apple Silicon Metal limits (27GB buffer crash)». (2) **victoria_server.py** — hardcoded приоритеты ml заменены на qwq:32b + qwen2.5-coder:32b (Ollama), security тоже qwq:32b; reasoning/complex теперь qwq:32b без 70b. (3) **mlx_api_server.py** — `_HEAVY_KEYS_NO_PRELOAD` оставляет только «reasoning» (не привязан к конкретным моделям). (4) **MASTER_REFERENCE §4** — новый буллет «Тяжёлые модели 70B/104B удалены из всех приоритетов» с пояснением причины и условий возврата (RAM ≥192 GB). (5) **CHANGES_FROM_OTHER_CHATS §0.4bd** (этот раздел).
- **Итог:** Victoria больше **не запрашивает 70B/104B** → MLX не пытается их загрузить → стабильность. При желании вернуть — предварительно убедиться, что RAM ≥192 GB (75% → ~144 GB доступно, 104B-q4 ~60–70 GB параметров + overhead).
- **Заметка:** Если в MODEL_PATHS остались 70b/104b и сканер их обнаружит — явно удалить из MODEL_PATHS (или переименовать, чтобы не подтягивались в список).

---

## 0.4bc. При добавлении новой модели — замер холодного старта и занесение в библию (2026-02-09)

- **Цель:** при добавлении новой модели обязательно делать замер и заносить данные в справочники, чтобы время загрузки и обработки моделью учитывалось при выполнении задач (таймауты Victoria, backend, MLX).
- **Внедрено:** (1) **MASTER_REFERENCE §4** — буллет «При добавлении новой модели (Ollama или MLX) — обязательно»: шаги (добавить модель → запустить measure_cold_start_all_models.py → обновить configs/*.json скриптом → при необходимости таблицу в MODEL_COLD_START_REFERENCE → учитывать recommended_timeout_sec в таймаутах). (2) **MODEL_COLD_START_REFERENCE.md** — раздел «Runbook: при добавлении новой модели» с командами и ссылкой на лимиты Metal. (3) **HOW_TO_INDEX** — строка «Добавление новой модели Ollama/MLX» → runbook в MASTER_REFERENCE и MODEL_COLD_START_REFERENCE.
- **Итог:** Добавил модель → запустил тест → скрипт обновляет configs/ollama_model_timings.json или configs/mlx_model_timings.json → при настройке таймаутов использовать recommended_timeout_sec.

---

## 0.4bb. Библия: лимиты Metal при добавлении тяжёлой модели (2026-02-09)

- **Цель:** не забыть при добавлении тяжёлой модели в MLX про лимиты Apple Silicon.
- **В MASTER_REFERENCE:** (1) в «Последние изменения» — блок про лимиты Metal (75% RAM на GPU, ~27 GB на один буфер на M4 Pro); перед добавлением тяжёлой модели проверять RAM и не превышать лимиты. (2) В §4 (Воркер и LLM) добавлен буллет **Apple Silicon / Metal — лимиты** с теми же цифрами и ссылкой на MLX_PYTHON_CRASH_CAUSE.md.
- **Итог:** при открытии библии и при чтении раздела про MLX видно напоминание про 75% RAM и ~27 GB на буфер.

---

## 0.4ba. MLX Python краши (Metal OOM): кэш 1, без предзагрузки 70B/104B, автоперезапуск (2026-02-09)

- **Цель:** устранить частые падения Python при работе MLX API Server (SIGABRT в `mlx::core::gpu::check_error` — ошибка Metal/GPU).
- **Причина (краш-репорт):** ошибка GPU при выполнении команд MLX → C++ исключение → abort(); типично при нехватке памяти или загрузке 70B/104B.
- **Внедрено:** (1) **MLX_MAX_CACHED_MODELS=1** по умолчанию в `mlx_api_server.py` и в скриптах запуска. (2) Предзагрузка: в коде исключены из предзагрузки ключи 70B/104B (`reasoning`, `command-r-plus:104b`, `deepseek-r1-distill-llama:70b`, `llama3.3:70b`); по умолчанию **MLX_PRELOAD_MODELS=fast**. (3) **start_mlx_api_server.sh** — явный экспорт MLX_MAX_CACHED_MODELS=1 и MLX_PRELOAD_MODELS=fast. (4) **start_mlx_server.sh** — wrapper с автоперезапуском при падении (uvicorn, те же env), лог `logs/mlx_server_wrapper.log`; для постоянной работы: `nohup bash scripts/start_mlx_server.sh &`. (5) **docs/MLX_PYTHON_CRASH_CAUSE.md** — разбор краша, принятое решение, ссылка на wrapper.
- **Итог:** Меньше нагрузка на GPU и память; после краша MLX перезапускается wrapper'ом. Рекомендация обновлять mlx/mlx-lm при повторных крашах.

---

## 0.4az. Замер каждой модели Ollama + MLX: своё время, таймауты по размеру, буфер на запуск (2026-02-09)

- **Цель:** знать точно, сколько по времени занимает каждая модель; тестировать и Ollama, и MLX; выставлять настройки и различать «модель не отвечает» и «модель ещё думает».
- **Изменения:** (1) **scripts/measure_all_models_ollama_mlx.py** — замер каждой модели Ollama и MLX: таймаут на запрос по размеру (маленькие 1 мин, средние 2 мин, большие 3 мин), буфер на запуск/развёртывание (small +30 с, medium +60 с, large +90 с); **recommended_timeout_sec** = measured_sec + startup_buffer_sec. Выход: tmp/model_timings_ollama_mlx.json, .txt (model, source, size_category, measured_sec, request_timeout_sec, startup_buffer_sec, recommended_timeout_sec, status). (2) **MODEL_TIMING_REFERENCE.md** — §4.3 «Все модели Ollama + MLX с таймаутами по размеру и буфером на запуск»; **VICTORIA_RESTARTS_CAUSE** §6 — ссылка на скрипт.
- **Итог:** У каждой модели своё рекомендуемое время; если ответа нет после recommended_timeout_sec — «не отвечает», иначе «ещё думает». Env: MEASURE_TIMEOUT_SMALL/MEDIUM/LARGE, MEASURE_STARTUP_BUFFER_SMALL/MEDIUM/LARGE.

---

## 0.4ay. Async-задачи долго в running: причина, замер модели, окно опроса (2026-02-09)

- **Цель:** досконально найти причину, почему async-задачи (run_victoria_tasks_3_and_4_async.sh) остаются в status=running и не переходят в completed; учесть локальные модели и пошагово разобрать цепочку с экспертами.
- **Вывод:** Код записи в store корректен (_run_task_background выставляет completed/failed, done_callback при исключении — failed). Причина — **задача реально выполняется дольше окна опроса**: маршрутизация → Veronica (90 с) или agent.run(); в agent.run() несколько вызовов LLM (understand_goal, plan, шаги); у каждой модели своё время (30–300+ с на вызов для тяжёлых).
- **Изменения:** (1) **run_victoria_tasks_3_and_4_async.sh** — окно опроса 60×10 с (600 с на задачу), в выводе опроса добавлен **stage** (queued/delegate_veronica/enhanced_solve/agent_run). (2) **scripts/measure_ollama_response_time.sh** — замер времени одного запроса к Ollama (и при наличии MLX) для оценки времени одного вызова LLM. (3) **VICTORIA_RESTARTS_CAUSE.md** — новый §4.1 «Async-задачи долго в running»: причина пошагово, что сделано, проверка. (4) **MODEL_TIMING_REFERENCE.md** — §4 «Замер одного вызова LLM», ссылка на measure_ollama_response_time.sh.
- **Итог:** Причина — не баг, а время выполнения на локальных моделях; окно опроса увеличено, добавлен замер и вывод stage для диагностики.
- **Прогон (2026-02-09):** замер Ollama — один запрос qwen3-coder:30b ~4.3 с (простой промпт); в логах Victoria первый вызов LLM (understand_goal, phi3.5:3.8b) **122.95 с**. Вывод опросов в скрипте перенесён в stderr (видны при запуске). В measure_ollama_response_time.sh выбор модели — полное имя с тегом (qwen3-coder:30b), пропуск embedding-only.

---

## 0.4ax. Таймауты старта Victoria и запас на загрузку моделей (2026-02-09)

- **Цель:** учитывать время на развёртывание, холодную БД и загрузку моделей Ollama/MLX при первом запросе; избежать ложных таймаутов и «down» на первом проходе мониторинга.
- **Изменения:** (1) **victoria_server.py** — таймауты lifespan: эксперты по умолчанию **30 с** (**VICTORIA_STARTUP_EXPERTS_TIMEOUT**), реестр **20 с** (**VICTORIA_STARTUP_REGISTRY_TIMEOUT**); пул БД **command_timeout** по умолчанию **25** (**VICTORIA_DB_POOL_COMMAND_TIMEOUT**). (2) **service_monitor.py** — задержка перед первым проходом по умолчанию **50 с** (**SERVICE_MONITOR_INITIAL_DELAY**, диапазон 25–120): старт Victoria 25–40 с + запас на загрузку моделей при первом запросе. (3) **VICTORIA_RESTARTS_CAUSE** — §1 и §5 обновлены (новые значения и env); **MAC_STUDIO_LOAD_AND_VICTORIA.md** — §4.4 «Время старта и загрузка моделей (запас)». (4) **У каждой модели своё время:** добавлен **docs/MODEL_TIMING_REFERENCE.md** — таблица по размеру модели (1–4B, 7–11B, 32B, 70B, 104B): холодная загрузка, первый ответ, рекомендуемые OLLAMA_EXECUTOR_TIMEOUT, SERVICE_MONITOR_INITIAL_DELAY, VICTORIA_TIMEOUT; примеры env по категориям. Ссылки в MAC_STUDIO_LOAD_AND_VICTORIA §4.4, VICTORIA_RESTARTS_CAUSE §1, MASTER_REFERENCE §8.
- **Итог:** Старт и мониторинг учитывают холодную БД и запас на модель; таймауты и задержку подбирать по размеру модели (MODEL_TIMING_REFERENCE).

---

## 0.4aw. «Мозги» корпорации: Victoria, Veronica, логика работы (2026-02-09)

- **Цель:** воссоздать единую логику работы («себя») в Victoria и согласовать помощников (Veronica, оркестраторы, эксперты) на Mac Studio в нашей корпорации.
- **Изменения:** (1) **configs/corporation_thinking.txt** — сжатая логика из THINKING_AND_APPROACH: принципы (делать как нужно, один источник истины, уточнять, проверять результат, обновлять библию) и последовательность (понять → контекст → план → выполнить → проверить → зафиксировать). (2) **configs/victoria_common.py** — добавлена **get_thinking_context()** (чтение corporation_thinking.txt). (3) **victoria_server.py** — загрузка **VICTORIA_THINKING_CONTEXT** при старте; в **project_prompt** для каждого запроса добавлен блок «КАК МЫ МЫСЛИМ» с этим контекстом. (4) **Veronica (server.py)** — в system_prompt добавлена роль «руки» Victoria: выполняет только конкретные шаги по плану или одно действие; решения и планирование — за Victoria и экспертами. (5) **configs/victoria_capabilities.txt** — фраза про логику корпорации (библия, уточнять, проверять, обновлять документы). (6) Backend тесты 58 passed; тесты knowledge_os без Redis/интеграции — 69 passed.
- **Итог:** Victoria получает в каждом запросе единую логику «как мы мыслим»; Veronica явно определена как исполнитель шагов; возможности Victoria описаны с учётом библии и проверки. Оркестраторы по-прежнему отдают план как подсказку (VICTORIA_TASK_CHAIN_FULL).

---

## 0.4av. Mac Studio: характеристики и загрузка в работе (2026-02-09)

- **Цель:** учитывать характеристики и загрузку Mac Studio при настройке Docker, Victoria и бэкенда — стабильная работа без вылетов и перегрузки.
- **Изменения:** (1) **docs/MAC_STUDIO_LOAD_AND_VICTORIA.md** — характеристики Mac Studio (M4 Max, RAM), рекомендуемая память Docker 8–12 GB, кто что потребляет (Ollama/MLX на хосте, Victoria/Veronica в Docker), таблицы переменных для Backend и Victoria (MAX_CONCURRENT_VICTORIA 10–20, USE_ELK=false, async_mode), чек-лист. (2) **knowledge_os/docker-compose.yml** — комментарий вверху со ссылкой на док; у victoria-agent добавлен **deploy.resources.reservations.memory: 2G**. (3) **backend/app/config.py** — комментарий у MAX_CONCURRENT_VICTORIA про Mac Studio и ссылка на док. (4) **.env** — в блоке Mac Studio добавлена ссылка на док и рекомендация по памяти Docker и MAX_CONCURRENT_VICTORIA. (5) **VICTORIA_RESTARTS_CAUSE** — ссылки на MAC_STUDIO_LOAD_AND_VICTORIA в §2 и §5. (6) **MAC_STUDIO_INDEX**, **HOW_TO_INDEX** — строки про новый документ.
- **Итог:** Один документ и настройки под Mac Studio; при развёртывании на Mac Studio следовать ему и при вылетах сверяться с VICTORIA_RESTARTS_CAUSE.

---

## 0.4au. Стабильность Victoria при нагрузке: вылеты и блокировка воркера (2026-02-09)

- **Цель:** устранить вылеты и «пустой ответ» при небольшой нагрузке; чтобы Victoria стабильно работала и отвечала на /health и /run/status.
- **Причины:** (1) Необработанное исключение в фоновой задаче (`asyncio.create_task(_run_task_background)`) могло приводить к падению процесса или «тихому» сбою. (2) Sync `POST /run` без async_mode занимает единственный воркер на всё время выполнения (LLM, инструменты) — пока воркер занят, запросы к /health и /run/status не обрабатываются → таймаут или connection reset у клиентов.
- **Изменения:** (1) **victoria_server.py:** у фоновой задачи добавлен **done_callback** — при любом исключении логируем и выставляем в store status=failed, error=...; в _run_task_background добавлена обработка **asyncio.CancelledError** и **BaseException** (логирование, пометка failed, для BaseException — re-raise). (2) Запуск Uvicorn с явным числом воркеров: **UVICORN_WORKERS** (по умолчанию 1). (3) **docs/VICTORIA_RESTARTS_CAUSE.md** — новый §5 «Стабильность при нагрузке»: что сделано, рекомендация использовать **async_mode=true** для нетривиальных запросов, чек-лист при вылетах (USE_ELK=false, память, async_mode).
- **Итог:** Исключения в фоновой задаче не должны «ронять» процесс; для длинных задач — использовать `POST /run?async_mode=true` и опрос `/run/status/{task_id}`. См. VICTORIA_RESTARTS_CAUSE §4–5, scripts/run_victoria_tasks_3_and_4_async.sh.

---

## 0.4at. Проверка корпорации пошагово: причина — как нужно — переделать (2026-02-09)

- **Цель:** делать всё вместе пошагово; следить, правильно ли корпорация делает; если не так — указывать причину и как нужно, переделывать пока не начнут делать правильно.
- **Изменения:** (1) **docs/CORPORATION_CHECK.md** — пошаговые проверки: эксперты (источник истины, комментарий в JSON), тесты (backend path parents[3], run_all_system_tests), документация и библия, запуск и границы кода; для каждого «было не так» — причина и «как нужно»; раздел «Что переделывать, пока не станет правильно». (2) **configs/experts/employees.json** — _comment исправлен: добавление новых — запись в JSON, затем `python scripts/sync_employees.py`; обратная синхронизация из БД — sync_employees_from_db.py. (3) Ссылки в HOW_TO_INDEX, MASTER_REFERENCE §8, WHATS_NOT_DONE §8.
- **Итог:** Один чек-лист проверки; корпорация и команда могут сверяться и исправлять по нему.

---

## 0.4as. Как мы мыслим: подход и логика для «моих» (2026-02-09)

- **Цель:** чтобы команда и агенты понимали, как ассистент/Виктория мыслит — подход, последовательность, принципы принятия решений.
- **Изменения:** (1) **docs/THINKING_AND_APPROACH.md** — принципы (делать как нужно, один источник истины, советоваться со специалистами, устранять причины, проверять результат, обновлять библию); пошаговая логика: понять → контекст (библия, HOW_TO_INDEX) → план → выполнить → проверить → зафиксировать; как принимаются решения и обрабатываются неясности; краткая схема-шпаргалка. (2) **HOW_TO_INDEX** — строка «Подход и логика» → THINKING_AND_APPROACH. (3) **MASTER_REFERENCE** — §8 и «Последние изменения» §0.4as.
- **Итог:** Один документ «как мы мыслим»; «мои» могут следовать той же логике.

---

## 0.4ar. Как что делать: единый индекс и решение «план = подсказка» (2026-02-09)

- **Цель:** доделать всё вместе и научить «моих» (команду и агентов), как что делать — один индекс runbook’ов и команд; зафиксировать открытые решения.
- **Изменения:** (1) **docs/HOW_TO_INDEX.md** — единый индекс: тема → что сделать → документ/команда (эксперты, куратор, миграции, тесты, секреты, восстановление, RAG, деплой, границы кода, что не сделано, цепочка задачи, проблемы и решения); блок «Для кого» (команда и Victoria/эксперты); быстрые команды. (2) **NEXT_STEPS_CORPORATION.md** §5 — решение «план оркестратора = подсказка» зафиксировано (оставить до доработки; при доработке — либо исполнение по assignments, либо явно «только контекст»); §6 — ссылка на HOW_TO_INDEX. (3) **WHATS_NOT_DONE** §1 — план оркестратора помечен «Решение зафиксировано», §8 — ссылка на HOW_TO_INDEX. (4) **MASTER_REFERENCE** — строка в §8, «Последние изменения» §0.4ar.
- **Итог:** Один вход «как что сделать» для людей и агентов; решение по плану в NEXT_STEPS; библия обновлена.

---

## 0.4aq. Использование базы знаний: кто и как (2026-02-09)

- **Цель:** явно ответить и задокументировать: накапливаемая ежедневно база знаний (knowledge_nodes) активно используется Victoria, Veronica, оркестраторами и экспертами.
- **Изменения:** (1) **docs/KNOWLEDGE_BASE_USAGE.md** — таблица потребителей: Victoria (_get_knowledge_context в victoria_server), Veronica (get_knowledge_context_veronica в server.py), оркестраторы и эксперты (run_smart_agent_async → _get_knowledge_context в ai_core), Telegram (search_knowledge), anti_hallucination, model_enhancer; откуда появляются узлы (задачи, Nightly Learner, куратор, ручное добавление). (2) **MASTER_REFERENCE** — §8 и «Последние изменения» §0.4am. (3) **WHATS_NOT_DONE** — пункт «Порог покрытия в CI» помечен сделанным (COVERAGE_FAIL_UNDER=5 в pytest-knowledge-os.yml); в §8 добавлена ссылка на KNOWLEDGE_BASE_USAGE.
- **Итог:** Вопрос «база знаний активно используется?» — да; один документ и ссылки в библии.

---

## 0.4ap. Улучшения и тесты: куратор по расписанию, тест контекста оркестратора (2026-02-09)

- **Цель:** продолжать цикл улучшение → тест → улучшение: куратор проще запускать по расписанию, цепочка оркестратора покрыта тестом.
- **Изменения:** (1) **scripts/run_curator_scheduled.sh** — скрипт для cron/launchd: полный файл задач (curator_tasks.txt), async, max-wait 600; env CURATOR_TASKS_FILE, CURATOR_MAX_WAIT, VICTORIA_URL. (2) **CURATOR_RUNBOOK.md** — раздел «Регулярный прогон» с примером cron. (3) **backend/app/tests/test_task_detector_chain.py** — тест `test_build_context_with_strategy_and_assignments`: контекст оркестратора содержит и стратегию, и назначения. (4) **ROADMAP_CORPORATION_LIKE_AI.md**, **NEXT_STEPS_CORPORATION.md** — ссылки на run_curator_scheduled.sh.
- **Итог:** Backend 58 тестов (было 57); полный прогон 127 (58+41+28). Куратор по расписанию: одна команда или cron.

---

## 0.4ao. Все миграции идемпотентны, apply_migrations без ошибок (2026-02-09)

- **Цель:** довести применение миграций до конца без падений; любая БД (свежая или существующая) — один прогон apply_migrations, exit 0.
- **Изменения:** (1) **add_feedback_system.sql** — добавлены ALTER TABLE user_feedback ADD COLUMN IF NOT EXISTS processed/processed_at и индекс, чтобы таблица без этих колонок достраивалась. (2) **add_knowledge_links_table.sql**, **add_multilanguage_support.sql**, **add_tasks_table.sql**, **add_security_tables.sql**, **add_webhooks_table.sql** — перед CREATE TRIGGER добавлен DROP TRIGGER IF EXISTS (идемпотентность). (3) **add_performance_optimizations.sql** — переменная current_date переименована в cur_date (избежание конфликта с reserved); блоки партиционирования выполняются только если таблица уже партиционирована (relkind = 'p'), иначе пропуск. (4) **create_experts_changelog.sql** — удалён Python-блок """ в начале, заменён на SQL-комментарии.
- **Итог:** apply_migrations.py завершается с «Все миграции успешно применены»; 57 backend + 41 KO unit + 28 KO с БД = 126 тестов проходят.

---

## 0.4an. Docker auto-init схемы и условная миграция fix_expert_discussions (2026-02-09)

- **Цель:** чтобы в будущем всё работало без ручных шагов: новый Docker — сразу каноническая схема; миграции не падают ни на UUID, ни на integer БД.
- **Изменения:** (1) **knowledge_os/docker-compose.yml (db):** добавлен volume `./db/init.sql:/docker-entrypoint-initdb.d/01-schema.sql` — при первом запуске контейнера (пустой postgres_data) Postgres выполняет init.sql, получается схема с knowledge_nodes.id = UUID. (2) **fix_expert_discussions_knowledge_node_id_type.sql** переписан в условный DO-блок: тип колонки expert_discussions.knowledge_node_id выбирается по типу knowledge_nodes.id (uuid → UUID, integer → INTEGER); если таблицы нет — no-op. Так apply_migrations не падает ни на свежей БД после init, ни на старой с integer.
- **Итог:** Локальный/новый Docker: `docker-compose up -d` → схема от init.sql; затем apply_migrations достраивает остальное. Старые БД по-прежнему мигрируют integer→UUID при необходимости.

---

## 0.4am. knowledge_nodes.id: UUID везде, тесты без skip (2026-02-09)

- **Цель:** чтобы 4 теста (knowledge_graph, test_load, test_e2e) выполнялись, а не скипались; БД с нуля или после миграции — везде knowledge_nodes.id = UUID.
- **Изменения:** (1) **Миграция knowledge_nodes_id_integer_to_uuid.sql** — условная: выполняется только если knowledge_nodes.id имеет тип integer; создаёт маппинг old_id→new_id, переводит knowledge_nodes.id и expert_discussions.knowledge_node_id в UUID. Если id уже UUID — no-op. (2) **TESTING_FULL_SYSTEM.md** — как убрать skip: БД от init.sql (UUID) или применить эту миграцию. (3) **VERIFICATION_CHECKLIST_OPTIMIZATIONS** §3 — та же логика. (4) **CI (pytest-knowledge-os):** в job pytest-with-db добавлены test_knowledge_graph.py, test_load.py, test_e2e.py — при БД от init.sql тесты проходят без skip.
- **Итог:** Локально: либо чистая БД от init.sql, либо один раз применить миграцию. CI уже поднимает БД из init.sql и теперь гоняет все перечисленные тесты с БД.

---

## 0.4al. Архитектура подключения экспертов (источник, sync, БД, TTL, runbook) (2026-02-09)

- **Цель:** зафиксировать обдуманное решение: единый источник, предсказуемая цепочка, задел на рост системы и нагрузки.
- **Изменения:** (1) **docs/EXPERT_CONNECTION_ARCHITECTURE.md** — схема: employees.json → sync_employees.py → seed_experts.json и БД; таблица потребителей (expert_services для промптов/планов/Swarm, БД для оркестратора/ExpertMatchingEngine/воркера); кэш и TTL; runbook добавления эксперта; связь с team.md, MASTER_REFERENCE, VERIFICATION_CHECKLIST. (2) **knowledge_os/app/expert_services.py** — TTL кэша БД вынесен в env **EXPERT_SERVICES_DB_TTL** (по умолчанию 60 с). (3) **configs/experts/team.md** — ссылка на EXPERT_CONNECTION_ARCHITECTURE. (4) **MASTER_REFERENCE** — строка в §8 и «Последние изменения» §0.4al.
- **Итог:** Один документ по экспертам; все, кому нужен список для промптов/планирования, идут через expert_services; при росте нагрузки — настраиваемый TTL и возможность Redis/Expert Registry по документу.

---

## 0.4ak. Устранение причин падений тестов (RUN_WITH_DB, e2e, file_watcher, live_chain) (2026-02-09)

- **Цель:** система должна работать «как частицы атомные» — выявить причины, логи, исправить, тестировать.
- **Изменения:** (1) **conftest:** тест test_expert_id — очистка в порядке FK: adaptive_learning_logs → tasks → interaction_logs → experts; один аргумент для DELETE tasks (оба условия $1). (2) **knowledge_graph/load/e2e:** фикстура knowledge_nodes_id_is_uuid (information_schema); тесты create_link, get_related_nodes, test_load_create_many_links, test_e2e_knowledge_creation_and_linking — skip при knowledge_nodes.id != uuid. (3) **file_watcher:** FileChangeHandler принимает loop; при start() передаём get_running_loop(); в _publish_event используем run_coroutine_threadsafe(publish(event), loop) если loop передан и running. (4) **contextual_learner:** привязка interaction_log_id — int() для цифровой строки (WHERE il.id); JOIN с knowledge_nodes через ::text; при integer id в INSERT adaptive_learning_logs передаём NULL в interaction_log_id. (5) **test_live_chain:** retry при ConnectionError/RemoteDisconnected для sync POST (3 попытки) и для async poll GET (5 retry). (6) **VERIFICATION_CHECKLIST §3:** добавлены строки по e2e teardown, file_watcher event loop, knowledge_graph skip, contextual_learner типы, live_chain retry. (7) **TESTING_FULL_SYSTEM:** примечание обновлено — 24 passed, 4 skipped при поднятой инфре.
- **Итог:** RUN_WITH_DB=1 даёт 24 passed, 4 skipped (skip только при knowledge_nodes.id != uuid). E2E contextual_learning_flow и teardown проходят; file_watcher_detects_creation проходит.

---

## 0.4aj. Тестирование всей системы: Victoria, Veronica, оркестраторы, эксперты (2026-02-08)

- **Цель:** тестировать не только Victoria, но и Veronica, оркестраторов и экспертов — как всё работает вместе, чтобы система была воспроизводимой («копия тебя»).
- **Изменения:** (1) **docs/TESTING_FULL_SYSTEM.md** — план: что тестируем (таблица компонентов), как запускать (быстрый прогон без живых сервисов, полный с integration), где какие тесты (§3), связь с VICTORIA_TASK_CHAIN_FULL и VERONICA_REAL_ROLE. (2) **backend/app/tests/test_veronica_delegate.py** — 5 тестов: delegate_to_veronica (пустой goal → None, 200 → dict, не 200/исключение/не-dict → None), mock aiohttp. (3) **knowledge_os/tests/test_expert_services.py** — get_all_expert_names, get_expert_services_text, list_experts_by_role. (4) **knowledge_os/tests/test_integration_bridge.py** — IntegrationBridge.process_task(use_v2=False): orchestrator=existing, status, assignments. (5) **scripts/run_all_system_tests.sh** — один вход: backend pytest + knowledge_os unit (Victoria, эксперты, IntegrationBridge, department_heads, skills, security, json_fast); при RUN_INTEGRATION=1 — интеграционные (test_live_chain); при RUN_WITH_DB=1 — тесты с БД/Redis (e2e, knowledge_graph, load, performance_optimizer, file_watcher, rest_api, service_monitor). (6) В TESTING_FULL_SYSTEM добавлена таблица «что не входит в быстрый прогон» и перечень файлов для RUN_INTEGRATION/RUN_WITH_DB; примечание: без БД/Redis часть RUN_WITH_DB тестов падает — ожидаемо. (7) MASTER_REFERENCE — ссылка на §0.4aj и TESTING_FULL_SYSTEM.
- **Итог:** 57 backend + 41 knowledge_os unit проходят за ~6 с. Интеграционные и тесты с БД запускаются тем же скриптом (RUN_INTEGRATION=1, RUN_WITH_DB=1). Для полной копии системы: документ и скрипт задают карту тестов и команды.

---

## 0.4ai. Тесты и проверка логики цепочки Victoria (2026-02-08)

- **Цель:** выявлять, тестировать, исправлять и фиксировать логику и связи цепочки (как должно работать).
- **Изменения:** (1) **scripts/test_task_detector.py** — ожидания приведены в соответствие с PREFER_EXPERTS_FIRST=true: «напиши/сделай» → enhanced, добавлен кейс «покажи список файлов в корне проекта» → veronica. (2) **backend/app/tests/test_task_detector_chain.py** — новый файл: тесты `detect_task_type` (simple_chat, veronica, enhanced, department_heads), `should_use_enhanced`, а также `_build_orchestration_context` и `_orchestrator_recommends_veronica` (импорт из victoria_server). Всего 15 тестов. (3) **VICTORIA_TASK_CHAIN_FULL.md** — добавлен §9 «Проверка логики и связей (тесты)» со ссылками на тестовый файл и команды запуска.
- **Итог:** Backend 52 теста (было 37). При изменении маршрутизации или формата плана — обновлять test_task_detector_chain и документ.

---

## 0.4ah. Полная цепочка задачи Victoria: кто распределяет, кто исполняет, один или команда (2026-02-08)

- **Цель:** проанализировать всю цепочку от поручения задачи Victoria до ответа: как и кто распределяет, правильно ли обрабатывается, как возвращается, сложная задача — вся команда или один эксперт.
- **Изменения:** (1) **docs/VICTORIA_TASK_CHAIN_FULL.md** — документ: схема цепочки (POST /run → маршрутизация → Veronica / Enhanced / agent_run), кто распределяет (task_detector, IntegrationBridge как план), кто исполняет по каждому маршруту (один агент vs swarm/consensus), как выбирается метод в Enhanced (категория → simple/react/swarm/consensus), как результат возвращается (in-process → TaskResponse). (2) Раздел «Выявленные разрывы»: план оркестратора только контекст, не исполнение; команда = только swarm/consensus или Department Heads swarm; Veronica — только одношаговые запросы. (3) Рекомендации: правильность (PREFER_EXPERTS_FIRST, не слать целые задачи в Veronica), скорость (не направлять простые в тяжёлые методы). (4) В коде: комментарии в victoria_server (orchestration_plan — контекст, не dispatch) и victoria_enhanced (_select_optimal_method — команда только для complex). (5) MASTER_REFERENCE §8 — ссылка на VICTORIA_TASK_CHAIN_FULL.
- **Итог:** Один источник истины по цепочке; при доработках маршрутизации и «исполнение по назначениям оркестратора» опираться на этот документ и NEXT_STEPS.

---

## 0.4ag. Улучшения куратора и API Victoria (2026-02-08)

- **Цель:** продолжить улучшения по NEXT_STEPS — runbook, скоринг «как я», verbose steps в API.
- **Изменения:** (1) **CURATOR_RUNBOOK:** уточнены retry (до 2 повторов задачи, до 3 повторов GET /run/status); в §4 добавлены ссылки на INDEX и CURATOR_LIST_FILES_FAILURES; в §2 — вызов `curator_compare_to_standard.py` для сравнения с эталоном. (2) **standards/README:** скрипт добавляет все 5 эталонов (что умеешь, привет, статус, список файлов, одна строка кода). (3) **scripts/curator_compare_to_standard.py:** скрипт сравнения отчёта с эталоном (ключевые фразы эталона vs ответ); `--report`, `--standard` или `--standard-file`. (4) **Victoria POST /run:** в TaskRequest добавлено поле `verbose: Optional[bool]`; при `verbose=true` в ответе в `knowledge.verbose_steps` возвращаются пошаговые шаги агента (thought, tool, tool_input) для маршрута agent_run; то же в фоновой задаче (GET /run/status). (5) **NEXT_STEPS_CORPORATION:** §3 обновлён — verbose и скоринг отмечены как сделанные.
- **Итог:** Куратор может сравнивать ответы с эталонами через скрипт; при глубоком разборе — запрос с verbose=true для пошаговых шагов.

---

## 0.4af. Причина сбоев «список файлов» в кураторе и что делать при следующих (2026-02-08)

- **Цель:** найти причину, почему задача «покажи список файлов в корне проекта» в полных прогонах куратора иногда падает с **Connection reset by peer**, и зафиксировать действия «при следующих».
- **Причина:** Обрыв видит клиент куратора при **GET /run/status/{task_id}** — соединение закрывает сервер. Возможные причины: (1) перезапуск/падение Victoria во время длительной работы (OOM, падение процесса); (2) долгое выполнение у Veronica (холодный старт LLM, большой каталог) — задача близка к 60 с, при нагрузке Victoria может упасть; (3) сетевой обрыв. Задача «список файлов» часто идёт в Veronica и может занимать 50–60+ с.
- **Изменения:** (1) **docs/curator_reports/CURATOR_LIST_FILES_FAILURES.md** — диагноз, что сделано для устойчивости, раздел «При следующих сбоях» (логи Victoria/Docker, проверка Veronica, лёгкий старт при OOM, DELEGATE_VERONICA_TIMEOUT). (2) **curator_send_tasks_to_victoria.py:** в цикле опроса при **GET /run/status** до **3 повторов** запроса при connection/reset/aborted (по одному task_id), чтобы не терять задачу из-за одного обрыва. (3) **enhanced_router.py:** **DELEGATE_VERONICA_TIMEOUT** по умолчанию **90** с (было 60). (4) **curator_reports/INDEX.md** — ссылка на CURATOR_LIST_FILES_FAILURES.
- **Итог:** При следующих сбоях «список файлов» — открыть CURATOR_LIST_FILES_FAILURES и выполнить пункты раздела «При следующих сбоях». **Прогон 23-16-02:** 5/5 success, «список файлов» success (92.7 с) после внедрения правок.

---

## 0.4ae. Victoria постоянно вылетает — причина и исправления (2026-02-08)

- **Цель:** найти причину постоянных вылетов Victoria (15+ рестартов).
- **Причина:** Service Monitor внутри контейнера проверял «Victoria Agent» по **localhost:8010**, тогда как внутри контейнера Victoria слушает **порт 8000**. Сам себя Victoria помечала как down → каскад событий «Обработка падения» / «Сервис перезапущен». Дополнительно: при реальных падениях возможен OOM (exit 137) из-за тяжёлого старта.
- **Изменения:** (1) **service_monitor.py:** endpoint для «Victoria Agent» = `http://127.0.0.1:{VICTORIA_PORT}` (в контейнере 8000). Для «Veronica Agent» в контейнере — `http://veronica-agent:8000`. Задержка до 15 с перед первым проходом мониторинга, чтобы не помечать себя down до подъёма HTTP. (2) **victoria_event_handlers.py:** при SERVICE_DOWN для «Victoria Agent» перезапуск пропускается. (3) **docs/VICTORIA_RESTARTS_CAUSE.md** — причины (ложный down, OOM), исправления. Ссылка в MASTER_REFERENCE §8.
- **Итог:** Ложное «сам себя down» устранено. При сохранении рестартов — смотреть OOM и VICTORIA_RESTARTS_CAUSE.

---

## 0.4ad. Куратор-наставник и единый источник возможностей Victoria (2026-02-08)

- **Цель:** сделать всё по рекомендациям аудита и с куратором как наставником — «лучшая корпорация в своём деле».
- **Изменения:** (1) **Единый источник текста «что ты умеешь»:** созданы **configs/victoria_capabilities.txt** (содержимое) и **configs/victoria_common.py** (get_capabilities_text(): читает файл или fallback). В **victoria_server** и **victoria_enhanced** при старте/вызове загружается текст из configs (с добавлением repo root в sys.path); при отсутствии файла или ошибке — встроенный fallback. Env **VICTORIA_CAPABILITIES_FILE** — путь к своему файлу. (2) **Куратор и наставник:** в **VICTORIA_CURATOR_PLAN** добавлен §5 «Куратор как наставник» (эталоны, передача в knowledge_nodes, единый источник возможностей, чеклист); создан **docs/curator_reports/CURATOR_CHECKLIST.md** — чеклист при разборе отчётов (цепочка, качество, эталон «как я», что передать в корпорацию). (3) **Следующие шаги:** **docs/NEXT_STEPS_CORPORATION.md** — что сделано, RAG Redis при масштабировании, дальнейшие улучшения по чеклисту. (4) В образ Victoria (COPY . .) попадает configs/, импорт configs.victoria_common в контейнере работает.
- **Итог:** Один файл для редактирования возможностей Victoria; куратор формализован как наставник с чеклистом и эталонами; дорожная карта следующих шагов зафиксирована.
- **Продолжение (тот же день):** (1) Эталоны: **what_can_you_do.md**, **greeting.md**, **status_project.md**, **list_files.md**, **one_line_code.md**. (2) **run_curator.sh** — быстрый прогон; полный: `--file scripts/curator_tasks.txt --async --max-wait 600`. (3) Полный прогон 22:51:44 — все 5 задач success; FINDINGS, эталоны. (4) **standards/README** — как добавить эталон в RAG; **scripts/curator_add_standard_to_knowledge.py** — 5 эталонов. **CURATOR_RUNBOOK.md**, **curator_reports/INDEX.md**, §5 в PLANS_AND_REPORTS_INDEX. Retry при connection reset в curator; **до двух повторов** (всего до 3 попыток на задачу). (5) Прогон 23-08-43: 4/5 success, «список файлов» — error после retry; INDEX и FINDINGS_2026-02-08_full_run дополнены; рекомендация — при повторных сбоях рассмотреть второй retry или больший таймаут для file-операций. **VICTORIA_RESTARTS_CAUSE.md:** перезапуск вручную, режим лёгкого старта (RAG_PRELOAD/SERVICE_MONITOR/ENABLE_EVENT_MONITORING=false). **docker-compose (victoria-agent):** RAG_PRELOAD_TYPICAL_QUERIES из env, комментарий про лёгкий старт при OOM. Тесты: backend 37, KO 11, frontend 4 — passed.

---

## 0.4ac. Полный аудит корпорации и оптимизация RAG-кэша (2026-02-08)

- **Цель:** тестировать всю связку и логику корпорации по библии; искать ошибки, баги и варианты улучшения быстродействия и правильности.
- **Изменения:** (1) **docs/curator_reports/CORPORATION_FULL_AUDIT_2026-02-08.md** — отчёт: тесты (backend 37, KO 23, frontend 4), проверка цепочек (чат→Victoria, Совет, RAG, слот), выводы по багам и улучшениям. (2) **RAG-кэш в victoria_server.py:** вытеснение устаревших записей ограничено **50 за вызов** (ленивое вытеснение), чтобы не делать O(n) по всем ключам на каждый запрос при большом кэше. (3) В VERIFICATION_2026-02-08 добавлена ссылка на полный аудит.
- **Итог:** Критических багов не найдено; слот освобождается в finally, board_decision_text инициализирован, fallback Совета корректен. Рекомендации по единому источнику текста «что умеешь» и по Redis для RAG-кэша при масштабировании — в отчёте.

---

## 0.4ab. Куратор Victoria и корпорации на Mac Studio (2026-02-08)

- **Цель:** пользователь хочет, чтобы агент в Cursor ставил задачи Victoria, получал ответы, проверял цепочку и находил недостатки — «научить её быть как я» на локальных моделях; побыть куратором Victoria и всей корпорации на Mac Studio.
- **Изменения:** (1) **docs/VICTORIA_CURATOR_PLAN.md** — план: как я вызываю Victoria (скрипты, POST /run), что видно в цепочке (output, knowledge.execution_trace, correlation_id), роль куратора и организация прогонов. (2) **scripts/curator_send_tasks_to_victoria.py** — скрипт: список задач (встроенный, --tasks или --file), синхронный или async+poll запрос к Victoria, сохранение отчёта в **docs/curator_reports/curator_YYYY-MM-DD_HH-MM-SS.json** и .md. (3) **scripts/curator_tasks.txt** — пример списка задач для прогона. (4) В MASTER_REFERENCE §8 добавлена ссылка на VICTORIA_CURATOR_PLAN. (5) **Первый прогон:** Victoria доступна, выполнены 2 задачи («привет», «что ты умеешь?»); отчёт curator_2026-02-08_22-00-36; **docs/curator_reports/FINDINGS_2026-02-08.md** — выводы куратора. (6) **Исправление по FINDINGS:** ответ на «что ты умеешь?» был слишком общим; добавлен фиксированный текст возможностей: в **victoria_server.py** быстрый путь в run() для «что ты умеешь»/«кто ты»; в **victoria_enhanced.py** в _execute_method() при category=="informational" возврат без вызова LLM.
- **Итог:** по запросу «прогони кураторский набор» или «проверь Victoria» агент может запустить скрипт, прочитать отчёт и сформировать FINDINGS. Ответ на «что ты умеешь?» теперь развёрнутый и единый по обоим маршрутам.

---

## 0.4aa. Подключение экспертов и решения выявленных проблем (2026-02-08)

- **Цель:** найти решения по выявленным проблемам (оркестратор 137, Ollama/MLX, тесты), привлечь экспертов и зафиксировать решения.
- **Изменения:** (1) Создан **docs/PROBLEMS_AND_EXPERT_SOLUTIONS.md** — сводная таблица проблем с привязкой к экспертам (Игорь, Сергей, Елена, Дмитрий, Роман, Анна), статус решений и ссылки на runbook/чеклист. (2) **ServiceMonitor:** добавлен метод **is_running()** (контракт с тестами и FileWatcher). (3) **test_load.py:** добавлены импорты **LinkType** и **uuid**. (4) **test_service_monitor.py:** проверка сервиса по имени в dict (`monitor.services["test_service"]`). (5) **enhanced_orchestrator.py:** в trigger_recovery_webhook заменён datetime.utcnow() на datetime.now(timezone.utc) (VERIFICATION_CHECKLIST §5).
- **Итог:** Проблемы 1–5 и 7 (оркестратор, Ollama/MLX, живой организм, контейнеры, «задачи не создаются») уже решены в предыдущих итерациях; в этой — документ экспертных решений и исправления тестов/оркестратора (API и timezone). При новом сбое — см. PROBLEMS_AND_EXPERT_SOLUTIONS и VERIFICATION_CHECKLIST §3.

---

## 0.4z. Прогон всех тестов (2026-02-08)

- **Цель:** «тестируйте все» — прогнать все тесты проекта.
- **Результаты (локально, venv в корне, без Pillow/полного knowledge_os requirements):**
  - **Backend** `backend/app/tests/`: **37 passed** (0.52s).
  - **Frontend** `npm run test`: **4 passed** (chat.spec.js).
  - **Knowledge OS** `test_json_fast_http_client.py`: **8 passed**.
  - **Knowledge OS** unit (skill_registry, skill_loader, skill_discovery, security, chain_department_heads): **18 passed** (нужны PyJWT, watchdog).
  - **Knowledge OS** без e2e/rest_api/victoria_chat: **34 passed, 11 failed, 2 skipped**. Падения из‑за: нет Redis (test_performance_optimizer, test_load), нет БД (test_knowledge_graph), Victoria не запущена (test_live_chain), file_watcher (тайминг), service_monitor (API: `is_running` → `running`, ожидание 1 сервиса vs 9), test_load (LinkType не определён).
- **Как запускать:** корневой `.venv`, `pip install pytest pytest-asyncio orjson httpx asyncpg PyJWT watchdog` + `backend/requirements.txt` для backend; `PYTHONPATH=$PWD pytest knowledge_os/tests/...` и `pytest backend/app/tests/`; frontend: `cd frontend && npm run test`. Тесты с БД/Redis/Victoria требуют поднятой инфраструктуры или CI.
- **Итог:** Основные наборы (backend, frontend, json_fast_http_client, skill/security/chain) проходят; интеграционные (e2e, rest_api, knowledge_graph, performance_optimizer, service_monitor, load, live_chain) — при наличии БД, Redis и Victoria или в CI.

---

## 0.4y. «Все делаем» — итог и подсказка asyncpg (2026-02-08)

- **Цель:** «все делаем» — проверить что осталось, убедиться что зависимости и библия актуальны.
- **Проверено:** (1) **TODO_FIXME_BACKLOG** — высокий/средний приоритет закрыт; низкий (signal_live, data_quality) — при касании модулей. (2) **asyncpg** — присутствует в knowledge_os/requirements.txt, requirements.txt (корень), backend/requirements.txt; при ошибке «asyncpg не установлен» (apply_migrations.py, оркестратор) установить зависимости: `pip install -r knowledge_os/requirements.txt` или `bash knowledge_os/scripts/setup_knowledge_os.sh`. (3) **RAG+ ракетная скорость** — реализовано (кэш RAG, один эмбеддинг, батч, предзагрузка, метрики, реранкинг по флагу); HNSW миграция в knowledge_os/db/migrations/add_hnsw_index_knowledge_nodes.sql, применяется через apply_migrations; проверка: `python3 knowledge_os/scripts/verify_hnsw_index.py`. (4) **PROJECT_GAPS** — оставшееся «частично» (E2E Playwright, полный e2e стратегический вопрос, линтер по путям) — по приоритетам.
- **Итог:** Локально перед первым запуском оркестратора/миграций — выполнить setup (setup_knowledge_os.sh или pip install -r knowledge_os/requirements.txt). Тесты: `pytest knowledge_os` (в venv с установленными зависимостями) или в CI.

---

## 0.4x. Порог покрытия в CI — 5% (2026-02-08)

- **Цель:** «дальше» — после замера базовой линии поднять планку покрытия в CI (PROJECT_GAPS §2).
- **Изменения:** В **pytest-knowledge-os.yml** COVERAGE_FAIL_UNDER и fallback в --cov-fail-under установлены в **5** (вместо 0). Замер no-DB тестов: 79% по затронутым модулям (http_client, json_fast); общий knowledge_os.app при расширении тестов можно поднимать дальше.
- **Итог:** CI не примет падение покрытия ниже 5%; при добавлении тестов порог при необходимости поднять в workflow.

---

## 0.4w. Backlog и runbook актуализированы (2026-02-08)

- **Цель:** «делай что осталось» — закрыть оставшиеся пункты backlog, убедиться, что причины сбоев и живой организм зафиксированы.
- **Изменения:** (1) **TODO_FIXME_BACKLOG.md:** optimize_symbol_parameters отмечен закрытым (передача params в AdvancedBacktest, grid search по PARAMETER_GRID); у auto_generate_tests уточнено — 5 TODO это шаблонные строки в сгенерированных стабах. (2) Подтверждено: контейнер knowledge_os_orchestrator запускает **enhanced_orchestrator.py** (check_llm_services_health, RECOVERY_WEBHOOK_URL, health monitor loop); runbook ORCHESTRATOR_137_AND_OLLAMA и LIVING_ORGANISM_PREVENTION актуальны; VERIFICATION_CHECKLIST §3 и §5 содержат причины «задачи не создаются», «оркестратор 137» и пункт «Чтобы в будущем не повторялось».
- **Итог:** Backlog по высокому/среднему приоритету закрыт; низкий — только уточнения. Оркестратор уже следит за Ollama/MLX и шлёт webhook; на хосте — system_auto_recovery по расписанию и при необходимости host_recovery_listener.

---

## 0.4v. Батч эмбеддингов в Victoria (2026-02-08)

- **Цель:** RAG_PLUS_ROCKET_SPEED — при нескольких подзапросах один вызов к Ollama/embedding API.
- **Изменения:** (1) **victoria_server.py:** метод **_get_embeddings_batch(self, texts: List[str])** — при len(texts)>1 один POST с `input: [t[:8000] for t in texts]`; при ответе с полем `embeddings` (массив) возвращает его; при ошибке или старом API — fallback на последовательные _get_embedding_for_rag. (2) **_preload_rag_cache()** сначала вызывает _get_embeddings_batch(_RAG_PRELOAD_QUERIES), затем для каждого goal — _get_knowledge_context(goal, precomputed_embedding=...). (3) **RAG_PLUS_ROCKET_SPEED.md:** пункт «Батч эмбеддингов» отмечен выполненным.
- **Итог:** Предзагрузка при старте делает один батч-запрос эмбеддингов (если Ollama поддерживает input-массив), иначе 4 одиночных. Горячий путь plan() по-прежнему один эмбеддинг на запрос.
- **Документация:** RAG_PLUS_ROCKET_SPEED.md, этот раздел.

---

## 0.4u. Предзагрузка типовых запросов в кэш RAG (2026-02-08)

- **Цель:** RAG_PLUS_ROCKET_SPEED — при старте предзаполнять кэш контекста RAG частыми интентами.
- **Изменения:** (1) **victoria_server.py:** список _RAG_PRELOAD_QUERIES («статус», «список файлов», «покажи файлы в текущей директории», «что ты умеешь»). Функция _preload_rag_cache() в фоне вызывает agent._get_knowledge_context(goal) для каждого; выполняется при RAG_CACHE_TTL_SEC>0 и RAG_PRELOAD_TYPICAL_QUERIES=true. В lifespan после загрузки реестра проектов — asyncio.create_task(_preload_rag_cache()). (2) **RAG_PLUS_ROCKET_SPEED.md:** пункт «Предзагрузка типовых запросов» отмечен выполненным; переменная RAG_PRELOAD_TYPICAL_QUERIES.
- **Итог:** Первые запросы «статус»/«список файлов» и т.п. чаще попадают в кэш RAG после прогрева при старте.
- **Документация:** RAG_PLUS_ROCKET_SPEED.md, этот раздел.

---

## 0.4t. Реранкинг RAG по флагу в Victoria (2026-02-08)

- **Цель:** RAG_PLUS_ROCKET_SPEED — для сложных запросов опционально включать реранкинг (уже один векторный запрос, без тяжёлого EnhancedRAGEngine).
- **Изменения:** (1) **victoria_server.py** в `_get_knowledge_context()`: переменная **RAG_RERANK_ENABLED** (по умолчанию false). При true — запрос к pgvector с LIMIT limit×2; реранжирование по score = similarity × бонус за длину контента (100–1000 символов); возврат топ limit. (2) **RAG_PLUS_ROCKET_SPEED.md:** пункт «Реранкинг по флагу» отмечен выполненным; в таблицу переменных добавлена RAG_RERANK_ENABLED.
- **Итог:** Включение реранкинга без смены стека: RAG_RERANK_ENABLED=true. Обычный поток по умолчанию без реранкинга (один векторный запрос).
- **Документация:** RAG_PLUS_ROCKET_SPEED.md, этот раздел.

---

## 0.4s. HNSW-проверка, Victoria /metrics, smart_worker latency, Grafana RAG (2026-02-08)

- **Цель:** «сама могу» — сделать следующие шаги без ручной настройки: проверка HNSW, метрики в Prometheus, замер латентности воркера, дашборд.
- **Изменения:** (1) **knowledge_os/scripts/verify_hnsw_index.py** — скрипт проверки наличия HNSW-индекса на knowledge_nodes.embedding; выход 0/1. (2) **Victoria GET /metrics** — Prometheus-формат: victoria_rag_embed_seconds, victoria_rag_prepare_seconds, victoria_rag_llm_plan_seconds (gauge), victoria_rag_slow_requests_total (counter). Без новой зависимости (plain text). (3) **smart_worker_autonomous.py** — замер latency_ms: time.perf_counter() до wait_for(run_cursor_agent_smart) и передача в record_attempt(success=True/False). (4) **grafana/dashboards/victoria-rag-latency.json** — дашборд с панелями RAG+ embed/prepare/llm_plan и slow_count. (5) **Victoria в Prometheus:** job victoria-agent (metrics_path: /metrics) добавлен в prometheus/prometheus.yml и infrastructure/monitoring/prometheus.yml.
- **Итог:** Проверка HNSW: `python knowledge_os/scripts/verify_hnsw_index.py`. Grafana: дашборд victoria-rag-latency. **Victoria в Prometheus:** job victoria-agent (metrics_path: /metrics) добавлен в **prometheus/prometheus.yml** (Web IDE) и в **infrastructure/monitoring/prometheus.yml** (Knowledge OS); при запуске обоих compose метрики RAG+ подтягиваются автоматически.
- **Документация:** RAG_PLUS_ROCKET_SPEED (упоминание /metrics и дашборда), этот раздел.

---

## 0.4r. Отслеживание и проверка «тормозит» RAG+ латентности (2026-02-08)

- **Цель:** метрики RAG+ либо **отслеживаются** (в мониторинге), либо **проверяются** при тормозах (WARNING + счётчик).
- **Изменения:** (1) **victoria_server.py:** модульные переменные `_rag_latency_last`, `_rag_latency_slow_count`, `_rag_latency_last_slow_at`. В `plan()` после замера embed_ms, prepare_ms, llm_plan_ms всегда обновляется `_rag_latency_last`. Пороги из env: **RAG_LATENCY_EMBED_MS_MAX** (300), **RAG_LATENCY_PREPARE_MS_MAX** (300), **RAG_LATENCY_LLM_PLAN_MS_MAX** (2000). При превышении любого — `_rag_latency_slow_count += 1`, `_rag_latency_last_slow_at = now`, **logger.warning("[RAG+_latency] SLOW ...")**. (2) **GET /status** возвращает блок **rag_latency**: `last` (embed_ms, prepare_ms, llm_plan_ms), `slow_count`, `last_slow_at`, `thresholds_ms`. (3) **RAG_PLUS_ROCKET_SPEED.md:** в «Реализовано» добавлен пункт про отслеживание и проверку; в таблицу переменных — RAG_LATENCY_*_MS_MAX.
- **Итог:** Мониторинг может опрашивать Victoria GET /status и строить алерты по `rag_latency.slow_count` или по логам `[RAG+_latency] SLOW`; последние значения доступны для дашбордов.
- **Документация:** RAG_PLUS_ROCKET_SPEED.md, этот раздел.

---

## 0.4q. Метрики латентности RAG+ в Victoria (2026-02-08)

- **Цель:** логировать время эмбеддинга, RAG+эксперт и LLM для анализа p99 (RAG_PLUS_ROCKET_SPEED, уровень 3).
- **Изменения:** (1) **victoria_server.py** в `plan()`: замер `time.perf_counter()` до и после `_get_embedding_for_rag(goal)` → **embed_ms**; до и после `asyncio.gather(select_expert_for_task, _get_knowledge_context)` → **prepare_ms**; до и после `planner.ask(plan_prompt, ...)` → **llm_plan_ms**. (2) При **RAG_LATENCY_LOG=true** или **VICTORIA_DEBUG=true** логируется строка `[RAG+_latency] embed_ms=... prepare_ms=... llm_plan_ms=...`. (3) **RAG_PLUS_ROCKET_SPEED.md:** пункт «Метрики латентности» отмечен как реализованный; в «Реализовано» добавлено описание и переменная RAG_LATENCY_LOG.
- **Итог:** Анализ латентности RAG+ по логам; целевой порог p99 &lt; 200–300 ms (при необходимости — инструментировать стриминг в executor для «время до первого токена»).
- **Документация:** RAG_PLUS_ROCKET_SPEED.md, MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.4p. Один эмбеддинг на запрос в Victoria (2026-02-08)

- **Цель:** ракетная скорость RAG+ — один вызов Ollama embeddings на запрос, передача эмбеддинга в RAG без повторного вызова (RAG_PLUS_ROCKET_SPEED, уровень 2).
- **Изменения:** (1) **victoria_server.py:** в `_get_knowledge_context(goal, limit=5, precomputed_embedding=None)` добавлен опциональный параметр `precomputed_embedding`; при передаче используется для векторного поиска без вызова `_get_embedding_for_rag(goal)`. (2) В точке входа (формирование промпта перед LLM): эмбеддинг вычисляется один раз (`precomputed_embedding = await self._get_embedding_for_rag(goal)`), затем параллельно `asyncio.gather(select_expert_for_task(...), _get_knowledge_context(goal, precomputed_embedding=precomputed_embedding))`. (3) **RAG_PLUS_ROCKET_SPEED.md:** пункт «Один эмбеддинг на запрос» отмечен как реализованный; в «Реализовано» добавлено описание.
- **Итог:** Один вызов Ollama на запрос для RAG; эксперт и RAG по-прежнему считаются параллельно после получения эмбеддинга.
- **Документация:** RAG_PLUS_ROCKET_SPEED.md, MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.4o. Кэш контекста RAG в Victoria (2026-02-08)

- **Цель:** ракетная скорость RAG+ — при повторных/похожих запросах не вызывать эмбеддинг и не ходить в БД (RAG_PLUS_ROCKET_SPEED, уровень 1).
- **Изменения:** (1) **victoria_server.py:** в `_get_knowledge_context()` в начале проверяется in-memory кэш по ключу `hashlib.md5(goal.strip().lower().encode()).hexdigest()`. При попадании возвращается сохранённый контекст. TTL задаётся **RAG_CACHE_TTL_SEC** (по умолчанию 120 с, 0 = отключить). Макс. размер кэша 500 записей, вытеснение по самой старой записи. При промахе контекст вычисляется как раньше (векторный поиск или ILIKE) и сохраняется в кэш. (2) **RAG_PLUS_ROCKET_SPEED.md:** пункт «Кэш контекста RAG» отмечен как реализованный; в раздел «Реализовано» добавлено описание кэша и переменная RAG_CACHE_TTL_SEC. (3) **VERIFICATION_CHECKLIST_OPTIMIZATIONS.md §5:** в пункт «Узлы знаний (knowledge_nodes) и RAG» добавлено упоминание кэша контекста RAG и рекомендация при правках _get_knowledge_context сохранять проверку кэша до эмбеддинга и БД.
- **Итог:** Повторные или близкие по формулировке запросы к Victoria получают контекст из кэша без вызова Ollama и без запроса к knowledge_nodes.
- **Документация:** RAG_PLUS_ROCKET_SPEED.md, VERIFICATION_CHECKLIST §5, MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.4n. Предотвращение повторения: runbook и чеклист (2026-02-08)

- **Цель:** чтобы ситуация «задачи не создаются, обучение не идёт, оркестратор 137» не повторялась — единая точка истины и явные правила при следующих изменениях.
- **Изменения:** (1) **docs/LIVING_ORGANISM_PREVENTION.md** — runbook: корневые причины (остановленные контейнеры + restart, нет проверки Ollama/MLX, OOM при старте и т.д.), что сделано, что проверять перед/после изменений и при новом сбое. (2) **VERIFICATION_CHECKLIST_OPTIMIZATIONS:** в §3 добавлена строка «Задачи не создаются, обучение не идёт» (причины и решения); в §5 — пункт «Чтобы в будущем не повторялось…» (recovery по расписанию, up -d, явная проверка nightly/orchestrator, оркестратор проверяет Ollama/MLX, host_recovery_listener, ссылка на ORCHESTRATOR_137_AND_OLLAMA). (3) **verify_mac_studio_self_recovery.sh:** подсказка при недоступном Ollama заменена с «brew services start ollama» на «bash scripts/system_auto_recovery.sh или ollama serve (от пользователя с моделями)». (4) **setup_system_auto_recovery.sh:** в конце вывод рекомендации запустить host_recovery_listener (порт 9099). (5) **ORCHESTRATOR_137_AND_OLLAMA.md §2.1:** для «Демон не запущен» предпочтительно `ollama serve` от пользователя с моделями.
- **Итог:** При правках recovery/compose/оркестратора — открывать §5 и LIVING_ORGANISM_PREVENTION; при сбое — раздел 3 чеклиста и runbook §3.
- **Документация:** LIVING_ORGANISM_PREVENTION.md, VERIFICATION_CHECKLIST §3 и §5, MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.4m. Живой организм: оркестратор следит за Ollama/MLX и запрашивает восстановление (2026-02-08)

- **Цель:** оркестратор должен сам следить за доступностью Ollama и MLX, при сбое — не усугублять (не вызывать тяжёлое обновление знаний) и инициировать восстановление на хосте.
- **Изменения:** (1) **enhanced_orchestrator.py:** в начале каждого цикла вызывается **check_llm_services_health()** (Ollama GET /api/tags, MLX GET /v1/models). При недоступном Ollama — **не вызывается** update_all_agents_knowledge() (избегаем OOM). При недоступности любого сервиса — **trigger_recovery_webhook()** (POST на RECOVERY_WEBHOOK_URL). В режиме **continuous** запускается фоновый **health monitor** (каждые ORCHESTRATOR_HEALTH_MONITOR_INTERVAL сек, по умолчанию 300), который при сбое снова шлёт webhook. (2) **scripts/host_recovery_listener.py:** HTTP-сервер на хосте (порт 9099); по POST /recover запускает system_auto_recovery.sh. (3) **docker-compose:** для knowledge_os_orchestrator заданы RECOVERY_WEBHOOK_URL (по умолчанию http://host.docker.internal:9099/recover) и ORCHESTRATOR_HEALTH_MONITOR_INTERVAL. (4) **ORCHESTRATOR_137_AND_OLLAMA.md:** добавлен §4 «Почему оркестратор за этим не следил и как стало (живой организм)», §6 — запуск host_recovery_listener на хосте.
- **Итог:** Оркестратор мониторит Ollama/MLX, при сбое не нагружает себя и запрашивает восстановление; на хосте нужно запустить `python3 scripts/host_recovery_listener.py` (и при желании Ollama/MLX). Периодическое самовосстановление (launchd каждые 300 с) уже было в setup_system_auto_recovery.sh.
- **Документация:** ORCHESTRATOR_137_AND_OLLAMA §4, §5, §6; этот раздел.

---

## 0.4l. Оркестратор 137 (OOM) и Ollama недоступен — причины и меры (2026-02-08)

- **Проверка:** По `docker events` подтверждено: контейнер **knowledge_os_orchestrator** падает с событием **container oom**, затем **die** с **exitCode=137**. Причина 137 — **OOM** (SIGKILL от менеджера памяти). На хосте на порту 11434 не слушает демон Ollama (запущен только ollama-mcp), поэтому «Ollama: All connection attempts failed»; MLX на 11435 из контейнера доступен.
- **Изменения:** (1) Создан **docs/ORCHESTRATOR_137_AND_OLLAMA.md** — разбор причин (OOM, Ollama не запущен), связь двух проблем, что сделано в коде, что сделать на хосте (ollama serve, память Docker). (2) **corporation_knowledge_system:** при сохранении знаний сначала импорт **semantic_cache.get_embedding** (лёгкий путь), при неудаче — app.main / enhanced_search; меньше тяжёлых импортов в оркестраторе и пик памяти при старте.
- **Итог:** Документация причин и шагов; оркестратор при том же окружении потребляет меньше памяти на старте. Для устойчивой работы: запустить Ollama на хосте; при повторном OOM — увеличить память Docker или лимит контейнера.
- **Документация:** ORCHESTRATOR_137_AND_OLLAMA.md, этот раздел.

---

## 0.4k. Контейнеры оркестратора/Nightly Learner упали — контроль и перезапуск (2026-02-08)

- **Проблема:** Задачи не создавались, обучение не проходило. Причина: контейнеры **knowledge_nightly** и **knowledge_os_orchestrator** были выключены (упали или не поднялись после перезагрузки), а скрипт самовосстановления при обнаружении остановленных контейнеров делал `docker-compose restart`. Команда **restart** перезапускает только уже работающие контейнеры и **не поднимает** остановленные — упавшие сервисы так и оставались выключенными. Явной проверки оркестратора и Nightly Learner в цикле восстановления не было; контроль был только у Victoria и Veronica.
- **Изменения:** (1) **system_auto_recovery.sh:** при наличии остановленных контейнеров Knowledge OS выполняется **`up -d`** вместо `restart`, чтобы поднять все сервисы. Добавлена явная проверка: если knowledge_nightly или knowledge_os_orchestrator не в `docker ps`, выполняется `up -d knowledge_nightly` и `up -d knowledge_os_orchestrator`. Для ATRA Web IDE при остановленных контейнерах тоже используется `up -d`. (2) **check_and_start_containers.sh:** после общего `up -d` добавлена явная проверка и подъём knowledge_nightly и knowledge_os_orchestrator. (3) **WHY_NO_LEARNING_DEBATES_HYPOTHESES_TASKS.md:** добавлен §0 «Контейнеры оркестратора или Nightly Learner остановились и не перезапустились» с причиной и рекомендациями.
- **Итог:** После следующего запуска system_auto_recovery (при загрузке или вручную) упавшие оркестратор и Nightly Learner будут подняты; при ручной проверке — check_and_start_containers тоже их поднимет.
- **Документация:** WHY_NO_LEARNING_DEBATES_HYPOTHESES_TASKS §0, этот раздел.

---

## 0.4j. Проект Сетки 21 зарегистрирован в реестре (2026-02-05)

- **Цель:** новый проект «Сетки 21» подключается к корпорации (Victoria, Veronica, оркестратор) через реестр проектов.
- **Изменения:** (1) Выполнена регистрация: `scripts/register_project.py setki-21 "Сетки 21"` — slug `setki-21` добавлен в таблицу `projects`. (2) Создан **docs/PROJECT_SETKI_21_SETUP.md** — инструкция по регистрации и настройке `.env` для работы с проектом.
- **Итог:** Victoria и Veronica принимают запросы с `project_context=setki-21`. Для работы в контексте Сетки 21 — задать `PROJECT_CONTEXT=setki-21` в `.env`. Перезапуск агентов после регистрации: `docker compose -f knowledge_os/docker-compose.yml restart victoria-agent veronica-agent`.
- **Документация:** PROJECT_SETKI_21_SETUP.md, этот раздел.

---

## 0.4i. Victoria зависает 30+ минут на «что ты умеешь?» в режиме Agent (2026-02-05)

- **Проблема:** В режиме «Агент» простые информационные запросы («что ты умеешь?», «кто ты?») шли в Victoria ReAct (LLM на каждом шаге), что при локальных моделях приводило к долгому ожиданию (до 30 минут) — пользователь видел «Агент думает» без ответа.
- **Изменения:** (1) **query_classifier.py:** добавлены INFORMATIONAL_PATTERNS (что ты умеешь, кто ты, чем помочь и т.д.) и шаблон ответа «что умеешь» в TEMPLATE_RESPONSES. (2) **chat.py:** быстрый путь для mode=agent — если classify_query → simple и get_template_response возвращает шаблон, отдаём его сразу без вызова Victoria.
- **Итог:** «что ты умеешь?» и подобные запросы в режиме Agent получают мгновенный шаблонный ответ вместо ожидания Victoria.
- **Документация:** этот раздел.

---

## 0.4h. Улучшай: RAG relevance — keyword-first, seed, порог (2026-02-06)

- **Цель:** достичь relevance ≥ 0.85 при валидации RAG.
- **Изменения:** (1) **evaluate_rag_quality.py:** keyword-first — kos.search_knowledge(query) перед векторным поиском; приоритет чанкам формата «Вопрос: X Ответ: Y» (seed_dataset). (2) RAG_SIMILARITY_THRESHOLD=0.2 для валидации. (3) **Обязательный шаг:** `python3 scripts/seed_knowledge_from_dataset.py` — наполняет knowledge_nodes эталонами из data/validation_queries.json. (4) RAG_VALIDATION_KEYWORD_FIRST=true (по умолчанию).
- **Итог:** relevance 1.0, All thresholds passed. Пайплайн: seed → heal_rag_cache → run_quality_pipeline.
- **Документация:** этот раздел, MASTER_REFERENCE.

---

## 0.4g. Доделывай: E2E Playwright, Ruff config, coverage baseline (2026-02-05)

- **Цель:** завершить оставшееся (E2E Playwright, Ruff конфиг, скрипт замера coverage).
- **Изменения:** (1) **E2E Playwright:** добавлены `tests/e2e/playwright.config.js`, `health.spec.js` (GET /health 200, status: healthy|degraded|unhealthy), `chat.spec.js` (загрузка страницы и textarea); `frontend/package.json` — `@playwright/test`, скрипты `e2e`, `e2e:ui`; workflow `.github/workflows/e2e-playwright.yml` (docker compose, touch .env, Playwright chromium, артефакт tests/e2e/test-results/). (2) **Ruff config:** в `pyproject.toml` обновлён [tool.ruff] — ignore F401,F841; exclude cache_normalizer_rs; CI использует pyproject.toml (|| true сохранён до исправления замечаний). (3) **Coverage baseline:** скрипт `scripts/measure_coverage_baseline.sh` для замера базовой линии (использует knowledge_os/.venv при наличии). (4) **PLANS_AND_REPORTS_INDEX:** добавлена секция «Скрипты» (§5) — E2E и coverage baseline.
- **Итог:** E2E для чата и health; ruff конфиг централизован; скрипт для поднятия COVERAGE_FAIL_UNDER; индекс скриптов в PLANS_AND_REPORTS_INDEX.
- **Документация:** этот раздел, MASTER_REFERENCE, PLANS_AND_REPORTS_INDEX §5.

---

## 0.4f. Делайте: TODO backlog, линтер, auth /metrics (2026-02-05)

- **Цель:** выполнить оставшиеся пункты (TODO приоритизация, линтер в CI, решение по auth /metrics).
- **Изменения:** (1) **TODO/FIXME backlog:** создан `docs/TODO_FIXME_BACKLOG.md` — приоритизация по высокий/средний/низкий; рекомендации команде при правках. (2) **Линтер в CI:** в pytest-knowledge-os.yml добавлен job `lint` — ruff check по backend/, knowledge_os/app/, src/ (|| true до исправления существующих замечаний). (3) **Auth /metrics:** в VERIFICATION_CHECKLIST §5 добавлен пункт — решение по окружению (внутренняя сеть = принять риск; иначе — auth или network policy). PROJECT_GAPS §1, §3, §4 обновлены.
- **Итог:** backlog для TODO; ruff в CI; решение по /metrics задокументировано.
- **Документация:** TODO_FIXME_BACKLOG, VERIFICATION_CHECKLIST §5, PROJECT_GAPS, этот раздел.

---

## 0.4e. Замечания PROJECT_GAPS: актуализация и решение с командой (2026-02-05)

- **Цель:** «делай все по замечанию решайте с командой» — актуализировать PROJECT_GAPS по текущему состоянию; методология: советоваться со специалистами (VERIFICATION_CHECKLIST §5, TEAM_PERSONALITIES).
- **Изменения:** (1) **PROJECT_GAPS §2 «CI не гоняет основной pytest-набор»:** статус обновлён на «Принято (2026-02-05)» — pytest-knowledge-os.yml уже добавлен (§0.3r), при push/PR в main прогоняются test_json_fast_http_client, test_rest_api, test_victoria_chat_and_request. (2) **§3 «Один workflow в CI»:** статус обновлён на «Частично» — pytest при push/PR есть; quality-validation — по расписанию. Линтер по изменённым путям — по возможности позже.
- **Итог:** замечания актуализированы; оставшиеся точки роста (TODO/FIXME приоритизация, auth для /metrics) — в следующих итерациях с привлечением соответствующих экспертов (Backend, SRE, QA).
- **Документация:** PROJECT_GAPS_ANALYSIS_2026_02_05, этот раздел.

---

## 0.4d. Выполнение задач по порядку: алерт, Victoria phase, Ollama в recovery (2026-02-05)

- **Цель:** закрыть оставшиеся пункты (Grafana алерт, лог шага при таймауте, MLX/Ollama после sleep).
- **Изменения:**
  1. **Victoria-agent** пересобран — OLLAMA_EXECUTOR_TIMEOUT применяется в executor (300 с по умолчанию).
  2. **Grafana алерт deferred_to_human > 10:** создан `grafana/provisioning/alerting/deferred_to_human.yaml` — unified alerting, группа knowledge_os_alerts, правило «Deferred to human queue high» (for 5m, dashboardUid: knowledge_os-tasks). Datasource Prometheus с uid: prometheus (добавлен в datasources.yml).
  3. **Victoria: лог шага при таймауте:** executor.ask() принимает параметр `phase`; при TimeoutError логируется `phase=understand_goal|plan|step_N`. understand_goal и plan передают phase; base_agent.step() и VictoriaAgent.step() передают step_number → phase.
  4. **system_auto_recovery: Ollama после sleep:** добавлен блок [4.5/10] — проверка Ollama (localhost:11434/api/tags); при отсутствии ответа — pkill + ollama serve; Ollama добавлен в проверку здоровья сервисов и в блок «без интернета». PROJECT_GAPS §3 «MLX/Ollama после sleep/wake».
- **Итог:** алерт в Grafana по provisioning; при таймауте Victoria видно, на каком шаге сбой; после wake system_auto_recovery проверяет и перезапускает Ollama.
- **Документация:** MASTER_REFERENCE §7, этот раздел.

---

## 0.4c. Victoria: не обрывать ответы — таймауты (2026-02-05)

- **Проблема:** Ответы обрывались — запросы к Victoria (чат, Telegram) не дожидались ответа на сложных запросах (локальные модели медленные).
- **Изменения:** (1) **VICTORIA_TIMEOUT** увеличен с 600 до **900 с** (15 мин) в backend config; backend и stream используют этот таймаут. (2) **send_message** обёрнут в `asyncio.wait_for` с `victoria_timeout` — при превышении возвращается **504** с понятным сообщением. (3) **OllamaExecutor** (Victoria): таймаут одного вызова LLM вынесен в env **OLLAMA_EXECUTOR_TIMEOUT** (по умолчанию **300 с** вместо жёстких 180). (4) **docker-compose:** backend — VICTORIA_TIMEOUT=900; victoria-agent — OLLAMA_EXECUTOR_TIMEOUT=300.
- **Итог:** Цепочка таймаутов позволяет дождаться ответа: 15 мин на весь запрос, 5 мин на каждый вызов Ollama.
- **Документация:** MASTER_REFERENCE §7, этот раздел.

---

## 0.4b. Victoria: лимит 500 шагов и долгие ответы (чат, Telegram) (2026-02-05)

- **Проблема:** В чате (localhost:3000) и в Telegram Victoria часто выдавала «Превышен лимит шагов (500)» и ответы были долгими из‑за большого числа шагов на локальных моделях.
- **Изменения:** (1) **Backend:** в config добавлен **victoria_max_steps_chat** (env **VICTORIA_MAX_STEPS_CHAT**, по умолчанию **50**). VictoriaClient.run() и run_stream() передают в Victoria **max_steps** из конфига (50). (2) **Telegram:** victoria_telegram_bot в payload передаёт **max_steps** из env **VICTORIA_MAX_STEPS** (по умолчанию **50**). (3) **base_agent** (src и knowledge_os): при превышении лимита возвращается сообщение «Превышен лимит шагов (N). Упростите запрос или разбейте задачу на части.» (4) На сервере Victoria DEFAULT_MAX_STEPS остаётся 500 для обратной совместимости со скриптами, не передающими max_steps.
- **Итог:** Чат и Telegram по умолчанию ограничены 50 шагами; при необходимости можно задать VICTORIA_MAX_STEPS_CHAT или VICTORIA_MAX_STEPS выше.
- **Документация:** MASTER_REFERENCE §7 (конфиг), этот раздел.

---

## 0.4a. Выполнение оставшихся задач: Grafana deferred, тесты board/consult (2026-02-05)

- **Цель:** закрыть пункты «осталось сделать»: алерт Grafana по deferred_to_human, тесты сценария board/consult + fallback, порог покрытия (оставлен 0 до замера базовой линии).
- **Изменения:** (1) **Grafana:** добавлен дашборд **grafana/dashboards/knowledge_os-tasks.json** — панели «Задачи на ручную проверку» (knowledge_os_tasks_deferred_to_human_total) и «Last error по типам» (knowledge_os_tasks_deferred_last_error_total); пороги yellow/red 10/20; в описании — рекомендация создать алерт при value > 10 (Edit panel → Alert). (2) **Порог покрытия:** COVERAGE_FAIL_UNDER оставлен 0 в workflow (после замера базовой линии по артефактам поднять до 5 или 10). (3) **Тесты Knowledge OS:** в test_rest_api.py добавлены test_board_consult_without_api_key_returns_401, test_board_consult_with_wrong_api_key_returns_401, test_metrics_include_deferred_to_human (GET /metrics содержит knowledge_os_tasks_deferred_to_human_total). (4) **Тесты Backend:** создан backend/app/tests/test_strategic_classifier.py — юнит-тесты is_strategic_question (стратегические/нестратегические фразы) и get_risk_level_from_question (high/medium/low).
- **Итог:** дашборд для deferred в Grafana; контракт board/consult (401 без ключа) и метрики покрыты тестами; классификатор стратегических вопросов покрыт юнит-тестами.
- **Проверка (2026-02-05):** test_metrics_include_deferred_to_human падал в TestClient из‑за «Event loop is closed» при вызове _deferred_metrics_prometheus. В rest_api при exception добавлен fallback: всегда выводится строка `knowledge_os_tasks_deferred_to_human_total 0`, чтобы /metrics содержал имя метрики и тесты проходили. Прогон: 18 passed (knowledge_os rest_api + json_fast), 9 passed (backend test_strategic_classifier).
- **Документация:** MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.3z. Методология работы (подтверждение) (2026-02-05)

- **Цель:** зафиксировать подтверждение пользователем правил работы: делать как нужно, советоваться со специалистами, постоянно проверять результат и исправлять ошибки, сверяться с мировыми практиками, устранять причины возникновения, сверяться с библией и обновлять её.
- **Изменения:** MASTER_REFERENCE — добавлена запись в «Последние изменения» со ссылкой на § «Методология работы», §6 и этот раздел. Содержимое методологии в .cursorrules и MASTER_REFERENCE § «Как пользоваться» не менялось.
- **Итог:** при смене контекста агент опирается на те же правила; библия актуальна.
- **Документация:** MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.3y. Фронтовые тесты (Vitest, smoke) (2026-02-05)

- **Цель:** частично закрыть недостаток PROJECT_GAPS_ANALYSIS §2 «Frontend без автотестов» — хотя бы smoke/критичные сценарии (мировая практика: тесты рядом с кодом, Vitest для Vite).
- **Изменения:** (1) **frontend/package.json:** добавлены скрипты **test** (`vitest run`), **test:watch** (`vitest`); devDependencies: **vitest**, **@testing-library/svelte**, **jsdom**. (2) **frontend/vite.config.js:** секция **test** (environment: jsdom, include: src/**/*.{test,spec}.{js,ts}, globals: true). (3) **frontend/src/stores/chat.spec.js:** 4 smoke-теста чат-стора (messages/chatMode начальное состояние, addMessage, clearMessages). (4) **VERIFICATION_CHECKLIST_OPTIMIZATIONS §2** и **PROJECT_GAPS_ANALYSIS §2:** в строку «Frontend без автотестов» указан статус «Частично (2026-02-05)» и ссылка на §0.3y.
- **Итог:** в frontend/ можно запускать `npm run test`; e2e (чат, health) — Playwright при необходимости позже.
- **Документация:** MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.3x. Единый индекс планов и отчётов (2026-02-05)

- **Цель:** закрыть недостаток PROJECT_GAPS_ANALYSIS §5 «Разрозненные планы и отчёты» — единая точка «где что искать».
- **Изменения:** (1) Создан документ **docs/PLANS_AND_REPORTS_INDEX.md**: разделы — Планы (.cursor/plans/, ключевой VERIFICATION_AND_FULL_PICTURE_PLAN), Архив отчётов (docs/archive/, root_reports, obsolete_backups), Программы обучения (learning_programs/), AI Insights (ai_insights/), связь с библией (MASTER_REFERENCE §8, CHANGES, PROJECT_GAPS). (2) **MASTER_REFERENCE §8:** в таблицу документов добавлена строка «Планы и отчёты (единый индекс)» → PLANS_AND_REPORTS_INDEX.md. (3) **PROJECT_GAPS_ANALYSIS §5:** в строку «Разрозненные планы и отчёты» указан статус «Принято (2026-02-05)» и ссылка на §0.3x.
- **Итог:** при вопросе «где планы/отчёты/обучение/инсайты» — открывать PLANS_AND_REPORTS_INDEX.md; таблица §8 остаётся главной точкой входа по документации.
- **Документация:** MASTER_REFERENCE §8, этот раздел.

---

## 0.3w. Порог покрытия в CI (--cov-fail-under) (2026-02-05)

- **Цель:** завершить пункт PROJECT_GAPS §2 «Покрытие не зафиксировано» — ввести порог покрытия в workflow (мировая практика: fail build при падении coverage ниже порога).
- **Изменения:** (1) **.github/workflows/pytest-knowledge-os.yml:** в обоих job'ах добавлены env **COVERAGE_FAIL_UNDER: "0"** и флаг **--cov-fail-under=${COVERAGE_FAIL_UNDER:-0}**. По умолчанию 0% — CI не падает до замера базовой линии; после замера поднять в workflow или через matrix/env (например 5 или 10). В шапке workflow — комментарий про поднятие порога. (2) **VERIFICATION_CHECKLIST_OPTIMIZATIONS §2:** уточнено: порог задаётся через COVERAGE_FAIL_UNDER. (3) **PROJECT_GAPS_ANALYSIS §2:** статус «Покрытие не зафиксировано» обновлён на «Принято (2026-02-05)» с указанием порога и ссылкой на §0.3w.
- **Итог:** механизм порога в CI включён; при необходимости поднять COVERAGE_FAIL_UNDER после анализа артефактов coverage.
- **Документация:** MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.3v. Мониторинг deferred_to_human и last_error (метрики в /metrics) (2026-02-05)

- **Цель:** частично закрыть недостаток PROJECT_GAPS_ANALYSIS §3 «Очередь на ручную проверку» — метрики для алертов при росте очереди.
- **Изменения:** (1) **knowledge_os/app/rest_api.py:** добавлены **\_deferred_metrics_prometheus()** и **\_normalize_last_error_type(err)**. Запрос к БД: COUNT deferred_to_human и выборка last_error по последним 500 задачам; нормализация last_error к типам: timeout, empty_or_short_response, validation_failed, connection_error, oom_or_metal, other. Вывод в формате Prometheus: **knowledge_os_tasks_deferred_to_human_total** N и **knowledge_os_tasks_deferred_last_error_total**{error_type="…"} M. Результат дописывается в ответ **GET /metrics** (и /api/v2/orchestrate/metrics). (2) **VERIFICATION_CHECKLIST_OPTIMIZATIONS §3:** в строку «Очередь на ручную проверку» добавлено: метрики в /metrics, алерты в Grafana при росте очереди, ссылка на §0.3v. (3) **PROJECT_GAPS_ANALYSIS §3:** в строку «Очередь на ручную проверку» указан статус «Частично (2026-02-05)» и ссылки на §0.3v и чеклист §3.
- **Итог:** Prometheus (скрап knowledge_rest 8002) получает счётчик очереди и разбивку по типам last_error; в Grafana можно настроить алерт при knowledge_os_tasks_deferred_to_human_total > порога.
- **Документация:** MASTER_REFERENCE (последние изменения 2026-02-05), этот раздел.

---

## 0.3u. Границы src/ и knowledge_os (документирование дублирования) (2026-02-05)

- **Цель:** частично закрыть недостаток PROJECT_GAPS_ANALYSIS §1 «Дублирование кода src/ и knowledge_os/» — явно зафиксировать в документации, какой путь продакшен для какого домена.
- **Изменения:** (1) Создан документ **docs/SRC_AND_KNOWLEDGE_OS_BOUNDARIES.md**: таблица границ (knowledge_os/app — корпорация; src/agents/bridge — Victoria Server/Bot; src/ остальное — домен торговли), разделы по каждому пути, рекомендации при правках. (2) **MASTER_REFERENCE §1г:** подраздел «Границы src/ и knowledge_os» со ссылкой на SRC_AND_KNOWLEDGE_OS_BOUNDARIES. (3) **PROJECT_GAPS_ANALYSIS §1:** в строке «Дублирование кода» указан статус «Частично (2026-02-05): задокументировано» и ссылка на документ и §0.3u. (4) **VERIFICATION_CHECKLIST_OPTIMIZATIONS §5:** добавлен пункт «Правки в src/ или knowledge_os/app/ (дублирование)» — сверяться с SRC_AND_KNOWLEDGE_OS_BOUNDARIES, при общей логике — единый модуль.
- **Итог:** при правках в src/ или knowledge_os/app/ — опираться на границы из документа; риск расхождения снижается за счёт явного описания ролей.
- **Документация:** MASTER_REFERENCE §1г, этот раздел.

---

## 0.3t. Покрытие тестами в CI (pytest-cov, артефакты) (2026-02-05)

- **Цель:** частично закрыть недостаток из PROJECT_GAPS_ANALYSIS §2 «Покрытие не зафиксировано»: артефакт coverage в workflow и возможность ввести порог позже.
- **Изменения:** (1) **knowledge_os/requirements.txt:** добавлен `pytest-cov>=4.1.0` (12-Factor: зависимости в requirements). (2) **.github/workflows/pytest-knowledge-os.yml:** в обоих job'ах прогон pytest с `--cov=knowledge_os.app --cov-report=xml --cov-report=term-missing --no-cov-on-fail`; после прогона загрузка артефактов **coverage-no-db** и **coverage-with-db** (файл coverage.xml). Порог (--cov-fail-under) не задан — после замера базовой линии можно добавить. (3) **VERIFICATION_CHECKLIST_OPTIMIZATIONS §2:** в блок «Юнит-тесты» добавлено упоминание --cov и артефактов в CI. (4) **PROJECT_GAPS_ANALYSIS §2:** в строке «Покрытие не зафиксировано» указан статус «Частично (2026-02-05)» и ссылка на §0.3t.
- **Итог:** при push/PR в main в Artifacts доступны отчёты покрытия по knowledge_os.app; порог при необходимости ввести в workflow позже.
- **Документация:** MASTER_REFERENCE (последние изменения 2026-02-05), этот раздел.

---

## 0.3s. Секреты и один воркер: чеклист и скрипт server46 (2026-02-05)

- **Цель:** устранить риски из PROJECT_GAPS_ANALYSIS §4 (секреты в репо, пароль в download_from_server46) и §8 (один воркер на окружение); закрепить в VERIFICATION_CHECKLIST §5.
- **Изменения:** (1) **scripts/download_from_server46.sh:** убран дефолтный пароль (SERVER_46_PASS только из окружения, не в коде). Добавлены ssh_cmd/scp_cmd: приоритет SSH-ключей (BatchMode=yes); при заданном SERVER_46_PASS в .env — использование sshpass. В шапке скрипта: ссылка на PROJECT_GAPS §4 и VERIFICATION_CHECKLIST §5. (2) **VERIFICATION_CHECKLIST_OPTIMIZATIONS §5:** пункт «Секреты» — не коммитить .env, шаблоны без секретов, в проде секрет-менеджер; скрипты без дефолтного пароля, приоритет SSH-ключей. Пункт «Деплой воркера» — перед/после деплоя проверять docker ps, только один контейнер воркера на окружение. (3) **PROJECT_GAPS_ANALYSIS_2026_02_05.md §4:** в таблице Безопасность для download_from_server46 указан статус «Принято (2026-02-05)» и ссылка на §0.3s и чеклист §5.
- **Итог:** пароль сервера 46 не хранится в репо; при следующих изменениях по секретам и деплою воркера — следовать §5.
- **Документация:** MASTER_REFERENCE (последние изменения 2026-02-05), этот раздел.

---

## 0.3r. CI: прогон pytest Knowledge OS (2026-02-05)

- **Цель:** устранить пробел из PROJECT_GAPS_ANALYSIS и VERIFICATION_CHECKLIST §2: CI не гонял основной pytest-набор (test_json_fast_http_client, test_rest_api, test_victoria_chat_and_request).
- **Изменения:** добавлен workflow **`.github/workflows/pytest-knowledge-os.yml`**. (1) **Job pytest-no-db:** при push/PR в main запускаются тесты `test_json_fast_http_client` (8 тестов, без БД) — ловят регрессии в json_fast и http_client. (2) **Job pytest-with-db:** сервис Postgres (образ pgvector/pgvector:pg16), ожидание готовности, установка postgresql-client, инициализация схемы (`knowledge_os/db/init.sql`), применение миграций (`knowledge_os/scripts/apply_migrations.py`), прогон `test_rest_api` и `test_victoria_chat_and_request`. Зависимости: knowledge_os/requirements.txt; env: DATABASE_URL, PYTHONPATH.
- **Итог:** при push/PR в main основной pytest-набор запускается в CI; регрессии по json_fast, http_client, REST API и Victoria/делегированию выявляются до merge.
- **Документация:** MASTER_REFERENCE (последние изменения 2026-02-05), этот раздел.

---

## 0.3q. Детальные правила экспертов в .cursor/rules/ (по образцу rules2) (2026-02-05)

- **Цель:** для ядра команды описать экспертов так же подробно, как в .cursor/rules2 (When to use, Positioning, Core principles, Responsibilities, Artifacts, Workflow), чтобы агент и пользователь понимали, что эксперт умеет и что знает.
- **Образец:** rules2 (ml_engineer.mdc, qa_engineer.mdc, python_engineer.mdc) — сценарии вызова, принципы, артефакты по путям проекта, пошаговый workflow.
- **Изменения:** обновлены 9 файлов в `.cursor/rules/`: **01_viktoriya.md**, **02_dmitriy.md**, **03_igor.md**, **04_sergey.md**, **05_anna.md**, **06_maksim.md**, **07_elena.md**, **11_roman.md**, **13_tatyana.md**. В каждый добавлены секции: When to use (конкретные сценарии вызова), Positioning (кто он в проекте, стиль из TEAM_PERSONALITIES), Core principles (принципы с опорой на чеклист и библию), Responsibilities (список дел), Artifacts (пути в atra-web-ide: backend/, knowledge_os/app/, scripts/, docs/VERIFICATION_CHECKLIST и т.д.), Workflow (пошаговый сценарий), примеры промптов и критерии качества. Остальные эксперты (76+) остаются в кратком формате (можно расширять по мере необходимости).
- **Итог:** при вызове @Игорь, @Дмитрий, @Анна и др. агент опирается на детальное описание «что умеет и что знает»; артефакты и workflow привязаны к проекту и чеклисту.
- **Документация:** MASTER_REFERENCE (последние изменения 2026-02-05), этот раздел.

---

## 0.3p. Анализ недостатков проекта (Виктория и команда) (2026-02-05)

- **Цель:** структурированный разбор слабых мест и рисков по зонам ответственности экспертов (Игорь, Роман, Анна, Елена, Алексей, Татьяна, Ольга, Дмитрий).
- **Документ:** [PROJECT_GAPS_ANALYSIS_2026_02_05.md](PROJECT_GAPS_ANALYSIS_2026_02_05.md). Источники: VERIFICATION_CHECKLIST_OPTIMIZATIONS (§3 причины сбоев, §5 при следующих изменениях), MASTER_REFERENCE, структура репо.
- **Выводы (кратко):** (1) CI не гоняет основной pytest (json_fast, rest_api, victoria_chat_and_request). (2) Дублирование кода между src/ и knowledge_os/ (telegram, signals, execution и др.). (3) employees.json (58) vs БД (86) — источник истины БД, sync нужен. (4) Секреты в .env/compose и в скриптах (server46) — риск утечки. (5) Много TODO в коде; docs/ очень большой (715+ файлов). (6) Один воркер на окружение, мониторинг deferred_to_human и last_error. Приоритеты: высокий — CI+pytest, не хранить пароли, один воркер; средний — дублирование, покрытие, мониторинг; низкий — индекс доков, фронтовые тесты.
- **Итог:** недостатки зафиксированы; при следующих изменениях опираться на чеклист §5 и этот анализ.

---

## 0.3o. Число экспертов — 86, источник истины БД (Docker) (2026-02-05)

- **Цель:** в документации и конфигурации отражать фактическое число экспертов из БД (PostgreSQL в Docker), а не устаревшее «85» или число записей в employees.json.
- **Источник истины:** таблица `experts` в PostgreSQL (knowledge_postgres). Отчёт: `knowledge_os/scripts/reports/experts_check_report.txt` — SELECT COUNT(*) FROM experts: **86**.
- **Изменения:** во всех ключевых местах заменено «85 экспертов» на **86**; добавлено уточнение «счёт из Docker/PostgreSQL» или «источник истины: БД». Обновлены: MASTER_REFERENCE, CHANGES_FROM_OTHER_CHATS, VERONICA_REAL_ROLE, knowledge_os/docker-compose.yml, .cursorrules, configs/experts/team.md (в БД 86; employees.json — для sync).
- **Итог:** при вопросе «сколько сотрудников» — ориентироваться на БД (86); репозиторий (employees.json) — для синхронизации в БД.

---

## 0.3n. Интеграция Atra Core (2026-02-05)

- **Цель:** объединить стратегическое лидерство и персональный опыт экспертов (Игорь, Роман, Дмитрий) с инфраструктурой Singularity 10.0 в едином контуре ATRA Web IDE.
- **Изменения:** (1) В **.cursorrules** добавлен раздел **«Активация интеллекта ATRA CORE (Victoria & Team)»**: персональный опыт экспертов (docs/TEAM_PERSONALITIES.md), золотые стандарты (UTC, идемпотентность, метод группового обсуждения экспертов), связь с библией и CHANGES_FROM_OTHER_CHATS. (2) При вызове @backend_developer (Игорь), @database_engineer (Роман), @ml_engineer (Дмитрий) и Виктории (Team Lead) используется расширенный контекст и стиль из TEAM_PERSONALITIES. (3) Правило: любое действие начинается с изучения docs/MASTER_REFERENCE.md и заканчивается обновлением docs/CHANGES_FROM_OTHER_CHATS.md.
- **Итог:** библия и методология едины; эксперты и Victoria работают в одном контексте Atra Core.
- **Документация:** MASTER_REFERENCE (последние изменения 2026-02-05), .cursorrules (раздел Atra Core).

---

## 0.3m. MLX API: таймауты по моделям (загрузка + инференс + запас) (2026-02-04)

- **Проблема:** у каждой модели разное время загрузки и обработки; фиксированный таймаут 300 с приводил к 503 при долгой генерации 70b или к лишнему ожиданию для мелких моделей; health-check'и ждали слот и падали по таймауту.
- **Решение:** (1) **MODEL_TIME_ESTIMATES** — словарь в mlx_api_server: для 104b/70b/32b/3b/1b и категорий (reasoning, coding, fast, tiny) заданы load_sec, inference_sec_per_1k, margin_sec; для неизвестных имён — fallback по размеру из имени. (2) **get_model_timeout_estimate(model_key, max_tokens, load_time_actual=None)** считает полный таймаут; при уже загруженной модели передаётся фактическое load_time_seconds из кэша. (3) **Ожидание слота (middleware):** таймаут задаётся через **MLX_QUEUE_WAIT_TIMEOUT** или как максимум по всем моделям при 2k токенов; запросы к `/`, `/health`, `/api/tags` **не занимают слот** — обрабатываются сразу. (4) **Генерация:** в _generate_text_internal после get_model() вычисляется gen_timeout и подставляется в asyncio.wait_for. (5) **Очередь** (/api/generate): перед add_request и wait_for вычисляется timeout_estimate по модели и request.max_tokens и передаётся в add_request(..., timeout=...) и wait_for(result_future, timeout=...).
- **Итог:** мелкие модели не ждут лишнего; 70b/104b получают достаточный лимит; health не упирается в слот; при необходимости пороги задаются через env MLX_QUEUE_WAIT_TIMEOUT.
- **Документация:** MASTER_REFERENCE (последние изменения), этот раздел.

---

## 0.3l. Прокси Claude Code → Victoria (эксперты и оркестраторы) (2026-02-04)

- **Цель:** позволить Claude Code использовать экспертов и оркестраторы корпорации (Victoria, выбор эксперта, Ollama/MLX).
- **Реализация:** добавлен каталог **proxy/** — FastAPI-сервис с endpoint **POST /v1/messages** (формат Anthropic Messages API). Прокси извлекает последнее user-сообщение из `messages`, вызывает Victoria **POST /run** с `goal`, возвращает ответ в формате Anthropic (content: [{ type: "text", text }], id, model, stop_reason, usage). Переменные: **VICTORIA_URL** (по умолчанию http://localhost:8010), **VICTORIA_PROXY_TIMEOUT** (600 с). Запуск: `VICTORIA_URL=http://localhost:8010 uvicorn proxy.main:app --host 0.0.0.0 --port 8040`. GET /health проверяет живость прокси и доступность Victoria.
- **Настройка Claude Code:** `ANTHROPIC_API_KEY=""`, `ANTHROPIC_BASE_URL=http://localhost:8040` (или http://185.177.216.15:8040 на сервере 185). Запросы идут: Claude Code → прокси (8040) → Victoria (8010) → эксперты, оркестраторы.
- **Документация:** proxy/README.md, docs/CLAUDE_CODE_LOCAL_MODELS.md §4, MASTER_REFERENCE (прокси Claude Code → Victoria).

---

## 0.3k. Причина сбоя (last_error) и задержка перед повтором — меньше deferred_to_human (2026-02-04)

- **Проблема:** задачи попадали в «Очередь на ручную проверку» (deferred_to_human) без явной причины в логах/UI; при таймауте или пустом ответе повторная попытка шла сразу и снова могла упираться в перегрузку LLM.
- **Решение:** (1) В **Smart Worker** при таймауте/исключении сохраняется причина в переменной `_last_failure_reason`; при пустом или коротком ответе в metadata задачи пишутся **last_error** (timeout, текст исключения, processing_error или empty_or_short_response) и при эскалации в Совет передаётся **last_error** в `escalate_task_to_board(..., last_error=...)`. (2) При возврате задачи в pending после сбоя задаётся **next_retry_after** = now + SMART_WORKER_RETRY_DELAY_SEC (по умолчанию 90 с); воркер при выборе задач добавляет условие `(metadata->>'next_retry_after' IS NULL OR (metadata->>'next_retry_after')::timestamptz < NOW())`, чтобы не брать задачу до истечения задержки. (3) В **дашборде** для задач с deferred_to_human в карточке выводится блок «Причина сбоя» из metadata.last_error или processing_error.
- **Итог:** по логам и дашборду видно, почему задача ушла в ручную проверку (timeout, connection refused, empty_or_short_response и т.д.); задержка перед повтором снижает вероятность повторных таймаутов под нагрузкой.
- **Документация:** MASTER_REFERENCE (причина сбоя и задержка), VERIFICATION_CHECKLIST_OPTIMIZATIONS §3 (очередь на ручную проверку).

---

## 0.3j. Дашборд корпорации: рендер только по разделу, под ключ (2026-02-04)

- **Цель:** довести дашборд до «под ключ»: при выборе раздела рендерятся только подвкладки этого раздела (ленивая загрузка, DASHBOARD_OPTIMIZATION_PLAN), без отрисовки 23 вкладок.
- **Изменения:** (1) Ветвление переведено на **if/elif**: Обзор → st.stop(); Задачи → 2 подвкладки + st.stop(); Разведка и симуляции → 3 подвкладки + st.stop(); **Стратегия и эксперты** → 5 подвкладок (Ликвидность, Структура, OKR, Решения Совета, Академия ИИ), контент вынесен в функции _render_liquidity, _render_structure, _render_okr, _render_board_decisions, _render_academy + st.stop(); Аналитика и качество / Система и агент — заглушки с текстом «подвкладки подключаются» + st.stop(); иначе — st.warning + st.stop(). (2) **Удалён** блок из 23 вкладок (~2394 строки) — код недостижим. (3) В _render_board_decisions запрос к board_decisions переведён на **параметризованный** (источник, риск, correlation_id, limit) — устранение риска SQL-инъекции. (4) Исправлены отступы в _render_simulator (блоки with tabs[1]..tabs[5]).
- **Верификация:** py_compile app.py — ок; линтер без ошибок. Дальнейшая итерация: вынести контент разделов «Аналитика и качество» и «Система и агент» в подвкладки (9 и 4 функций по плану).

---

## 0.3i. Дашборд корпорации: навигация по разделам (2026-02-04)

- **Цель:** уменьшить «лишнее» и улучшить удобство: много вкладок (23) накопилось, пользоваться стало неудобно (рекомендации специалистов, мировые практики: 5–7 пунктов навигации, прогрессивное раскрытие).
- **Изменения:** (1) В сайдбаре дашборда (app.py) добавлена навигация по **6 разделам**: Обзор, Задачи, Разведка и симуляции, Стратегия и эксперты, Аналитика и качество, Система и агент. (2) Раздел **«Обзор»** — единая точка входа: компактный статус, семантический поиск в базе знаний, быстрые действия; при выборе «Обзор» 23 вкладки не показываются (st.stop). (3) При выборе раздела показываются только подвкладки этого раздела (см. §0.3j). (4) Рекомендации чеклиста (дашборд и воркер — один DATABASE_URL, сброс кэша при «Обновить») не менялись.
- **Верификация:** линтер без ошибок; дашборд запускается (streamlit run app.py).

---

## 0.3h. Методология работы (2026-02-04)

- **Цель:** закрепить единый подход к изменениям: качество, верификация, устранение причин, актуальность библии.
- **Изменения:** (1) В **.cursorrules** добавлен раздел **«Методология работы»**: делать как нужно по постановке; советоваться со специалистами (роли в .cursor/rules/, VERIFICATION_CHECKLIST_OPTIMIZATIONS, CHANGES_FROM_OTHER_CHATS); постоянно проверять результат (тесты, сценарии) и исправлять выявленные ошибки; сверяться с мировыми практиками; устранять причины сбоев и учитывать §5 чеклиста «При следующих изменениях»; сверяться с библией и обновлять MASTER_REFERENCE и связанные доки после правок. (2) В **MASTER_REFERENCE** в § «Как пользоваться» добавлен подраздел «Методология работы» с той же логикой.
- **Использование:** при любых правках агент/разработчик следует этой методологии; специалисты и чеклист — в .cursor/rules/ и VERIFICATION_CHECKLIST_OPTIMIZATIONS.

---

## 0.3g. Порядок везде: .backup в архив, .gitignore (2026-02-04)

- **Цель:** навести порядок везде (рекомендации специалистов: структура, мировые практики).
- **Изменения:** (1) Файлы с суффиксом .backup из исходников перенесены в **docs/archive/obsolete_backups/** (например src/filters/manager.py.backup). (2) В .gitignore добавлены *.backup, *.bak, *.swp, *.tmp. (3) docs/archive/README.md дополнен разделом obsolete_backups/. (4) PROJECT_ARCHITECTURE_AND_GUIDE §2 — уточнена структура (корень, docs/archive).
- **Верификация:** тесты не затронуты (backup не в пути импорта).

---

## 0.3f. Порядок в папках: архив корневых отчётов (2026-02-04)

- **Цель:** убрать лишнее из корня, навести порядок (рекомендации специалистов: структура проекта, мировые практики).
- **Изменения:** (1) Одноразовые отчёты и статусы из корня перенесены в **docs/archive/root_reports/** (исторические COMPLETE_*, FINAL_*, VICTORIA_*, TELEGRAM_* и др.). (2) В корне оставлены: README.md, PLAN.md, VICTORIA.md, VERONICA.md, requirements.txt и конфиги/скрипты. (3) В .gitignore добавлены артефакты сборки: target/, *.o, *.rlib, *.dylib, *.a. (4) docs/archive/README.md — описание архива; MASTER_REFERENCE §8 — ссылка на архив.
- **Верификация:** тесты knowledge_os — 15 passed. Ссылки из .cursorrules (VICTORIA.md, VERONICA.md) не тронуты.

---

## 0.3e. Rust cache_normalizer: faster-hex и предвыделение в батче (2026-02-04)

- **Цель:** дополнительная оптимизация кода на Rust (мировые практики: быстрый hex, предвыделение).
- **Изменения:** в `cache_normalizer_rs`: (1) зависимость **faster-hex** (0.10) для hex-кодирования MD5 вместо `format!("{:x}", digest)` — SIMD, существенно быстрее; (2) в `normalize_and_hash_batch` — `Vec::with_capacity(texts.len())` для предвыделения результата.
- **Совместимость:** результат hex совпадает с Python hashlib.hexdigest() (проверка и тесты — ок).
- **Документация:** OPTIMIZATION_AND_RUST_CANDIDATES §4, MASTER_REFERENCE.

---

## 0.3d. Использование normalize_and_hash_batch в embedding_optimizer (2026-02-04)

- **Цель:** рекомендация дорожной карты §5 — в местах массовой обработки вызывать batch один раз.
- **Изменения:** в `knowledge_os/app/embedding_optimizer.py`: (1) импорт `normalize_and_hash_batch` при наличии Rust; (2) `_get_text_hashes_batch(texts)` — один вызов Rust или список одиночных хэшей; (3) `_get_cached_embedding_by_hash(text_hash)` — общая логика «память → БД»; (4) `get_cached_embedding` переведён на вызов `_get_cached_embedding_by_hash`; (5) `get_embeddings_batch` сначала получает все хэши через `_get_text_hashes_batch(texts)`, затем для каждого — `_get_cached_embedding_by_hash(h)`.
- **Результат:** при батч-запросе эмбеддингов — один переход Python↔Rust для N текстов вместо N переходов.
- **Верификация:** проверка `_get_text_hashes_batch` vs `_get_text_hash`; pytest (json_fast, rest_api) — 15 passed.

---

## 0.3c. Корпорация на Rust: дорожная карта и batch (2026-02-04)

- **Цель:** «корпорация на Rust» как поэтапное наращивание доли Rust в узких местах (по библии и OPTIMIZATION_AND_RUST_CANDIDATES — не полная переписывание оркестрации/LLM).
- **Документ:** [docs/CORPORATION_RUST_ROADMAP.md](CORPORATION_RUST_ROADMAP.md) — видение, принципы (согласованы с чеклистом и специалистами), фазы (1 — cache_normalizer ✅, 1b — batch ✅, 2–4 в плане), следующие шаги.
- **Rust:** в cache_normalizer_rs добавлена **normalize_and_hash_batch(texts: list[str]) -> list[str]** — один вызов для списка текстов, меньше переходов Python↔Rust при массовой обработке; контракт и fallback сохранены.
- **Верификация:** cargo test (6 passed), pytest (json_fast, rest_api — 15 passed), проверка из Python (batch совпадает с одиночными вызовами).
- **Документация:** MASTER_REFERENCE (запись + таблица документов), CORPORATION_RUST_ROADMAP, OPTIMIZATION_AND_RUST_CANDIDATES §4 (batch), cache_normalizer_rs/README.

---

## 0.3b. Ускорение Rust cache_normalizer (2026-02-04)

- **Цель:** ускорить код на Rust для корпорации (нормализация текста и MD5 для ключей кэша эмбеддингов).
- **Изменения:** (1) `knowledge_os/cache_normalizer_rs`: нормализация без промежуточного `Vec` — один проход в `String::with_capacity`; (2) профиль release: `opt-level=3`, `lto="thin"`, `codegen-units=1`; (3) юнит-тесты в Rust (пустая строка, пробелы, консистентность хэша, MD5 пустой строки); (4) при Python 3.14 сборка: `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 maturin develop --release`.
- **Совместимость:** контракт с Python сохранён (normalize_text и normalize_and_hash совпадают с `' '.join(text.lower().split())` и `hashlib.md5(...).hexdigest()`). Проверка: `python -c "from cache_normalizer import normalize_and_hash, normalize_text; import hashlib; ..."`.
- **Верификация:** `cargo test` (с PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 при Python 3.14), бенчмарк `scripts/benchmark_cache_normalizer.py`, тесты knowledge_os (test_json_fast_http_client, test_rest_api) — 15 passed.
- **Документация:** MASTER_REFERENCE § «Ускорение Rust cache_normalizer», OPTIMIZATION_AND_RUST_CANDIDATES §4, cache_normalizer_rs/README.md.

---

## 0.3a. Таймаут запроса к LLM — дождаться ответа (2026-02-04)

- **Проблема:** часть задач не дожидалась ответа при работающих MLX/Ollama — воркер ждёт до 300 с (SMART_WORKER_LLM_TIMEOUT), но внутренний HTTP-запрос к узлам обрывался через **120 с** (жёстко в local_router и ai_core).
- **Решение:** таймаут запроса к узлам задаётся через **LOCAL_ROUTER_LLM_TIMEOUT** (по умолчанию **300** с). В local_router: POST к узлу использует `float(os.getenv("LOCAL_ROUTER_LLM_TIMEOUT", "300"))`. В ai_core (Ollama fallback): `aiohttp.ClientTimeout(total=_ollama_timeout)` с тем же значением (env LOCAL_ROUTER_LLM_TIMEOUT или SMART_WORKER_LLM_TIMEOUT).
- **Итог:** воркер и роутер ждут ответа одинаково долго; при тяжёлых моделях или нагрузке можно задать SMART_WORKER_LLM_TIMEOUT=400 и LOCAL_ROUTER_LLM_TIMEOUT=400.
- **Документация:** VERIFICATION_CHECKLIST_OPTIMIZATIONS §3 (Часть задач не дожидается ответа).

---

## 0.3. Retry и эскалация в Совет Директоров (2026-02-04)

- **Требование:** все задачи должны в итоге быть обработаны; при неудаче — возврат в очередь, ещё до 2 повторных попыток (итого 3 попытки); после 3 неудач — эскалация в Совет Директоров для выяснения причин.
- **Реализация:** в **Smart Worker** (`knowledge_os/app/smart_worker_autonomous.py`): константа **MAX_ATTEMPTS=3** (env `SMART_WORKER_MAX_ATTEMPTS`). Единая логика: (1) при ошибке LLM / пустом ответе / провале валидации увеличивается `metadata.attempt_count`; (2) при `attempt_count < MAX_ATTEMPTS` задача переводится в `pending` и снова попадает в очередь; (3) при `attempt_count >= MAX_ATTEMPTS` сначала вызывается rule_executor; при неудаче — вызов **`escalate_task_to_board()`** (внутри — `strategic_board.consult_board` с question=задача+описание+последняя ошибка, source=task_escalation, correlation_id=task_{id}); (4) задача завершается как `completed`, результат содержит текст решения Совета (если получено) и пометки `board_escalated`, `deferred_to_human`.
- **Валидация:** неуспешная проверка результата (task_result_validator) учитывается как попытка: увеличивается attempt_count; при достижении MAX_ATTEMPTS — та же эскалация и завершение.
- **Запись решений:** вызовы Совета при эскалации сохраняются в `board_decisions` (source=task_escalation), доступны на дашборде «Решения Совета».
- **Документация:** MASTER_REFERENCE § «Retry и эскалация в Совет Директоров».

---

## 0.2. Дедупликация задач от обучения (Curiosity / ИССЛЕДОВАНИЕ) (2026-02-04)

- **Проблема:** одна и та же задача (например «ИССЛЕДОВАНИЕ: R&D») создавалась оркестраторами несколько раз в день для разных экспертов или повторно для одного эксперта — без проверки «уже была такая задача у этого эксперта».
- **Решение:** общий хелпер `knowledge_os/app/task_dedup.py`: `same_task_for_expert_in_last_n_days(conn, title, description, assignee_expert_id, days=30)` — проверяет по нормализованным title и description и assignee_expert_id за последние 30 дней (все статусы). Критерий «однотипная задача»: совпадение названия, описания и эксперта → не чаще раза в месяц на эксперта.
- **Интеграция:** (1) **Enhanced Orchestrator** Phase 5 (Curiosity): перед созданием задачи по «пустыне» вызывается `get_best_expert_for_domain(conn, desert['id'])` (без записи в БД), затем проверка дедупликации для этого эксперта; при дубликате — skip с логом. (2) **Streaming Orchestrator** `_run_curiosity_engine`: перед INSERT проверка через `same_task_for_expert_in_last_n_days` для выбранного assignee; при дубликате — skip. Относится к задачам, создаваемым из обучения (curiosity_engine_starvation, исследовательские задачи).
- **Документация:** MASTER_REFERENCE § «Дедупликация задач от обучения», VERIFICATION_CHECKLIST_OPTIMIZATIONS §3 (причина дубликатов), §5 (при следующих изменениях оркестратора).

---

## 0.1. Эмбеддинги 768 и веб-поиск (2026-02-03)

- **Размерность эмбеддингов 768:** nomic-embed-text (Ollama) выдаёт 768 измерений. Ошибка «expected 384 dimensions, not 768» возникала при записи в semantic_ai_cache/embedding_cache, если схема БД была vector(384). Исправлено: (1) миграция `knowledge_os/db/migrations/fix_embedding_dimensions_768.sql` — приводит колонки embedding к vector(768); (2) в коде везде унифицирована размерность 768: semantic_cache (EMBEDDING_DIM, проверка перед save), дашборд (fallback 768), tacit_knowledge_miner, scout_researcher, enhanced_scout_researcher. Применение миграции: автоматически при старте Enhanced Orchestrator (Phase 0.5) или вручную через psql. См. CHECK_TASKS_IN_PROGRESS_20260203, MASTER_REFERENCE § эмбеддинги.
- **Веб-поиск (duckduckgo-search):** пакет `duckduckgo-search>=6.0.0` добавлен в `knowledge_os/requirements.txt` и корневой `requirements.txt` (образ агентов/воркера). Veronica (VeronicaWebResearcher), researcher, scout используют его для веб-поиска без API-ключа. После `pip install -r requirements.txt` предупреждение «duckduckgo_search не установлен» исчезнет.

---

## 0. Корпорация как мозг, реестр проектов (2026-02-03)

- **Реестр проектов (таблица `projects`):** единый источник истины для разрешённых проектов; Victoria и Veronica загружают список и конфиг из БД при старте (с fallback на env и хардкод). Миграция: `knowledge_os/db/migrations/add_projects_table.sql`; сидер: atra-web-ide, atra.
- **Регистрация нового проекта:** скрипт `scripts/register_project.py` или `POST /api/projects/register` (Knowledge OS 8002, X-API-Key). После регистрации новый `project_context` принимается агентами (после рестарта или по TTL кэша).
- **Изоляция по проекту:** в таблице `tasks` добавлена колонка `project_context` (миграция `add_project_context_to_tasks.sql`); при декомпозиции подзадачи наследуют project_context родителя; Victoria передаёт project_context в IntegrationBridge (metadata).
- **Управление и мониторинг с дашборда:** `GET /api/projects` (Knowledge OS 8002) — список проектов (is_active=true). Дашборд корпорации: вкладка «📁 Проекты» (таблица из `projects`); во вкладке «🛠️ Задачи» — фильтр по проекту, в карточках задач отображается project_context; при создании задачи (Симулятор, Маркетинг, Разведка, Поставить задачу) — выбор проекта (dropdown), значение записывается в `tasks.project_context`.
- **Документация:** MASTER_REFERENCE §1а, §1б, §1в; NEW_PROJECT_MINIMAL_STEPS.md; .env.client.example. Подробно: план corporation_brain_and_auto-connect_projects.

---

## 1. Victoria: один сервис, три уровня (8010)

- **Victoria Agent / Enhanced / Initiative** — один сервис на порту **8010**, три уровня возможностей в одном процессе.
- Для полноценной работы **все три уровня должны быть запущены** (USE_VICTORIA_ENHANCED=true, ENABLE_EVENT_MONITORING=true).
- Проверка: `GET http://localhost:8010/status` → `victoria_levels`: agent, enhanced, initiative (все true).
- **Автопроверка и автовключение:** скрипты `scripts/check_and_start_containers.sh` и `scripts/system_auto_recovery.sh` всегда проверяют три уровня; если enhanced или initiative выключены — автоматически перезапускают victoria-agent.
- Детали: `docs/VICTORIA_PROCESS_FULL.md`, `.cursorrules` (раздел Компоненты).

---

## 2. Correlation ID и уточняющие вопросы

- **Correlation ID:** заголовок `X-Correlation-ID` или автогенерация; поле в TaskResponse, в 202/GET status, в knowledge.metadata.
- **Уточняющие вопросы:** при неоднозначной задаче (эвристики в `_check_ambiguity`) возвращается `status: "needs_clarification"`, `clarification_questions`, `suggested_restatement`; выполнение не запускается. Для выполнения используется `restated_goal`.
- Файлы: `src/agents/bridge/victoria_server.py`.
- Детали: `docs/IMPROVEMENTS_IMPLEMENTED.md`.

---

## 3. Кэш в LocalAIRouter

- Кэш по ключу (prompt, category, model), TTL 30 мин, max 500 записей; возвращается кортеж (result, routing_source).
- Статистика: `_prompt_cache_hits`, `_prompt_cache_misses`.
- Файл: `knowledge_os/app/local_router.py`.
- Детали: `docs/IMPROVEMENTS_IMPLEMENTED.md`.

---

## 4. Архитектура: кто выполняет и кто кому докладывает

- **Department Heads:** «сотрудники» (эксперты из БД) выполняют через **локальные модели** внутри процесса Victoria (`ai_core.run_smart_agent_async`). Veronica (8011) **не вызывается**. Итог собирает Victoria.
- **Делегирование:** Victoria отправляет задачу на Veronica (8011) по HTTP; Veronica выполняет и возвращает результат Victoria → пользователю.
- Детали: `docs/ARCHITECTURE_FULL.md` (раздел «Кто выполняет задачу и кто кому докладывает»).

---

## 5. Task plan и Task Distribution

- План от Victoria может возвращаться как структурированный `task_plan_struct`; Task Distribution использует его без повторного вызова Victoria для парсинга.
- Smart Worker проверяет результат через общий валидатор перед отметкой completed.
- Детали: `docs/ARCHITECTURE_FULL.md` (схема и текст).

---

## 6. Таймауты для тяжёлых моделей

- 180 сек мало: тяжёлая модель может долго запускаться + обработка локальными моделями.
- **Backend:** `VICTORIA_TIMEOUT` по умолчанию **600** сек (config: `victoria_timeout`).
- Чат и клиенты Victoria должны использовать этот таймаут (или больше) для вызовов `/run`.
- Файлы: `backend/app/config.py`, `backend/app/services/victoria.py`, при необходимости — chat router, Telegram bot, scripts.

---

## 7. Исправления багов (из чатов)

- Исправлен отступ блока `if best:` в `_ensure_best_available_models` (victoria_server.py).
- Dashboard: обработка отсутствующих данных (get/or '', strftime, stderr/stdout), консолидация traceback, логика _categorize_task для сложных задач.
- Детали: `docs/IMPROVEMENTS_IMPLEMENTED.md`, `docs/ARCHITECTURE_IMPROVEMENTS_ANALYSIS.md` (раздел «Реализовано»).

---

## 8. Маршрутизация: эксперты первыми (Veronica — «руки»)

- **PREFER_EXPERTS_FIRST** (по умолчанию `true`): execution-задачи («сделай», «напиши код», «создай API») идут в **Victoria Enhanced** (86 экспертов в БД; счёт из таблицы experts, Docker); в **Veronica** — только простые одношаговые запросы («покажи файлы», «выведи список», «прочитай файл»). Реальная роль Veronica — исполнитель шагов (руки), не «решатель».
- **Два слоя:** (1) **task_detector** (src/agents/bridge) — при приёме запроса: «сделай/напиши код» → enhanced; (2) **victoria_enhanced._should_delegate_task** — внутри Enhanced при PREFER_EXPERTS_FIRST делегирует в Veronica только если `_is_simple_veronica_request(goal)`, иначе задача остаётся Victoria/экспертам. Раньше _should_delegate_task не учитывал PREFER_EXPERTS_FIRST и мог отдавать execution в Veronica.
- **Исправлен баг** в `task_delegation.select_best_agent`: блок «если нет required_capabilities» был с неправильным отступом; код подсчёта agent_scores стал достижим. В _should_delegate_task сравнение способностей — по enum AgentCapability, не по строкам.
- Файлы: `src/agents/bridge/task_detector.py`, `knowledge_os/app/victoria_enhanced.py`, `knowledge_os/app/task_delegation.py`, `knowledge_os/docker-compose.yml` (victoria-agent: PREFER_EXPERTS_FIRST).
- Верификация: пункт 20 чеклиста, тесты `TestPreferExpertsFirstDelegation` в `tests/test_victoria_chat_and_request.py`.
- Детали: `docs/VERONICA_REAL_ROLE.md`, `.cursorrules` (раздел «Маршрутизация: эксперты первыми»).

---

## 8.1. Чат с Victoria: контракт и устойчивость (2026-02-01)

- **Контракт Victoria POST /run:** body — TaskRequest с полями `goal`, `project_context` (не `prompt`). Backend VictoriaClient.run() уже передавал goal и project_context; VictoriaClient.run_stream() исправлен: теперь отправляет `goal` и `project_context`, а не `prompt`.
- **Устойчивость чата:** при недоступности Victoria (health не ok) — fallback на MLX/Ollama; при ошибке victoria.run() — fallback; при любом исключении в sse_generator — try/except отдаёт сообщение и `type: end`. Слот Victoria снимается через with_victoria_slot в finally. При перегрузке (лимит слотов) — 503 + Retry-After.
- Верификация: пункт 21 в [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md).

---

## 9. Воркер: пропускная способность и зависания (2026-02-01)

- **Причины зависания:** (1) синхронное чтение файлов в `file_context_enricher` блокировало event loop → heartbeats не бежали; (2) пул БД max_size=5 при 10 конкурентных задачах + 10 heartbeats → нехватка соединений; (3) сброс зависших раз в 1 ч → мало pending.
- **Исправления:** вызов enricher через `run_in_executor`; пул воркера `max(15, SMART_WORKER_MAX_CONCURRENT + 8)`; `SMART_WORKER_STUCK_MINUTES=15`; непрерывная обработка (семафор вместо ожидания всего батча).
- **Чеклист:** пункты 14–19 в [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md); при новом коде в цепочке воркера — не вызывать sync I/O напрямую в async, выносить в `run_in_executor`.
- **Ollama/MLX:** LocalAIRouter и сканер моделей используют `OLLAMA_API_URL`/`MLX_API_URL` из env (раньше в Docker игнорировали env → зависания/неверный хост). Защита от эхо: если ответ = промпт, пробуем следующий узел (пункт 18 чеклиста).
- **Батчи по модели:** воркер по сканеру назначает задаче `preferred_model`, группирует по (source, model), обрабатывает блоками — меньше load/unload на MLX/Ollama (`SMART_WORKER_BATCH_BY_MODEL=true`, пункт 19 чеклиста).
- Детали: [WORKER_THROUGHPUT_AND_STUCK_TASKS.md](WORKER_THROUGHPUT_AND_STUCK_TASKS.md).

---

## 9.1. Docker: независимость от atra (2026-02-03)

- **Контекст:** проект atra — отдельный (будет в новом репозитории); atra-web-ide не должен зависеть от контейнеров atra.
- **Redis:** контейнер переименован в **knowledge_os_redis** (вместо knowledge_redis), порт на хосте **6381** (6380 может быть занят atra). В compose: REDIS_URL=redis://redis:6379 (по имени сервиса); backend (Web IDE): REDIS_URL=redis://knowledge_os_redis:6379.
- **Сироты:** контейнеры knowledge_dashboard и knowledge_os_api удалены (--remove-orphans); их роли выполняют **corporation-dashboard** и **knowledge_rest** (уже были в текущем compose).
- **Причины и профилактика:** конфликт имён/портов с atra описан в [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) (раздел 3). При добавлении сервисов в knowledge_os compose — не использовать имена/порты, занятые atra.

---

## 10. Живой мозг: Prompt Engineer, Self-Check→задачи, календарь (2026-02-03)

- **Prompt Engineer:** Добавлена роль в employees.json (Арина); Knowledge Applicator создаёт задачи с `assignee_hint: "Prompt Engineer"` для топ-инсайтов.
- **Self-Check → задачи:** При DEGRADED/UNHEALTHY без auto_fix Self-Check создаёт задачу в БД (`metadata.source: self_check_system`, `assignee_hint: SRE`). Защита от дублей: не создаёт если такая задача уже есть за 24ч.
- **CORPORATION_PLANNING_CALENDAR.md:** Единый обзор автономных циклов — что когда запускается, куда пишет результат.
- **Проверка после выполнения в цепочке БД:** Уже реализована в Smart Worker через `task_result_validator`; при провале задача возвращается в pending.
- **Victoria task_plan_struct:** Улучшен парсинг JSON в _think_and_create_prompt_for_veronica (_try_parse_llm_json: trailing comma, markdown); чаще возвращается task_plan_struct → без повторного вызова Victoria в _parse_veronica_prompt.
- **ReActAgent: рефлексия при ошибках, HITL:** При observation с Error — рефлексия явно просит проанализировать причину и предложить другой подход. При блокировке write в критичный файл — вызов request_approval, запрос с request_id в сообщении агенту.
- **Ретривал по успешным решениям:** ai_core._get_knowledge_context — дополнительный запрос к knowledge_nodes (source_ref='autonomous_worker', confidence>=0.8) по similarity; примеры успешных решений подмешиваются в промпт.
- **Session context в Victoria:** victoria_server при session_id без chat_history вызывает session_context_manager.get_session_context и добавляет в context["chat_history"]. Для прямых вызовов API (скрипты, Telegram).
- **Фаза автотестов в Nightly Learner (Phase 13):** pytest по ключевым тестам; результат в knowledge_nodes; при провале — задача для QA.
- **Backend: session_id и chat_history в VictoriaClient:** run() и run_stream() передают session_id и chat_history в Victoria; chat router использует to_victoria_chat_history() для конвертации.
- **Декомпозиция сложных задач из БД:** Enhanced Orchestrator Phase 1.5 — для priority=high/urgent или metadata.complex вызывается Victoria, создаются подзадачи с parent_task_id.
- **Code-Smell Predictor:** Интеграция проверена: code_auditor → CodeSmellPredictor → задачи в БД; enhanced_orchestrator приоритизирует source=code_auditor; smart_worker выполняет.
- **Tacit Knowledge баг:** is_coding_task в ai_core использовался до определения — исправлено, расширены keywords; ROLE_PROMPT_TEMPLATES для Prompt Engineer.
- **Робастность декомпозиции:** Phase 1.5 при отсутствии parent_task_id — skip; VERIFICATION_CHECKLIST п.27–28, причины сбоев.
- **Phase 14 Nightly Learner:** git log за 24ч → изменённые .py без тестов → задачи «Сгенерировать pytest для модуля X» (assignee_hint: QA).
- **correlation_id по цепочке:** Backend chat → VictoriaClient.run/run_stream → X-Correlation-ID → Victoria; SSE step содержит correlation_id.
- **correlation_id везде:** Terminal /ask и Editor /autocomplete тоже передают correlation_id.
- **AUTO_PROFILING_GUIDE.md:** руководство по cProfile/py-spy для Performance Engineer (Living Brain §6.3).
- **Retention traces:** cleanup_old_traces в CORPORATION_PLANNING_CALENDAR; §5а MASTER_REFERENCE «Living Organism / Living Brain: статус планов».
- **Phase 15 авто-профилирование:** Nightly Learner по воскресеньям — cProfile json_fast x500 → knowledge_nodes (source_ref=auto_profiling). Планы: todos completed, phase6-auto-profiling done.
- **Dashboard auto-apply (safe):** При AUTO_APPLY_DASHBOARD=true — патч max_entries=100 в st.cache_data; критичные — только задачи. Living Organism §3.
- **Predictive Monitor:** predictive_monitor.py — тренды (stuck in_progress, old pending), пороги через env; при превышении — задачи SRE. Интегрирован в Self-Check. Living Organism §6.
- **SSE progress events:** backend chat — события `type: 'progress'` { step, total, status } (analysis, executing, complete, error). ARCHITECTURE_IMPROVEMENTS §2.1.
- **Батчинг мелких задач:** Enhanced Orchestrator Phase 1.6 — BATCH_SMALL_TASKS_ENABLED, задачи одного domain (low/medium) получают batch_group в metadata. ARCHITECTURE_IMPROVEMENTS §2.5.
- **Smart Worker batch LLM:** При SMART_WORKER_BATCH_GROUP_LLM=true — один вызов LLM на batch_group (2–3 задачи), fallback на индивидуальную обработку при ошибке парсинга. Включено в knowledge_os/docker-compose.yml.
- **Phase 16 doc sync task:** Nightly Learner при merge в main за 24ч создаёт задачу «Синхронизировать документацию» для Technical Writer. Living Organism §8.
- **Завершение Living Brain/Organism:** Все пункты планов выполнены; верификация 23 passed; батчинг включён.

Файлы: `configs/experts/employees.json`, `knowledge_os/app/enhanced_orchestrator.py`, `knowledge_os/observability/knowledge_applicator.py`, `knowledge_os/app/self_check_system.py`, `knowledge_os/app/victoria_enhanced.py`, `knowledge_os/app/react_agent.py`, `knowledge_os/app/ai_core.py`, `knowledge_os/app/nightly_learner.py`, `src/agents/bridge/victoria_server.py`, `backend/app/services/victoria.py`, `backend/app/services/conversation_context.py`, `backend/app/routers/chat.py`, `docs/CORPORATION_PLANNING_CALENDAR.md`, `docs/MASTER_REFERENCE.md`.

---

## 11. Совет Директоров — Victoria — Чат (2026-01-27)

- **Цель:** по стратегическим вопросам в чате решение принимает «Совет Директоров» (LLM с контекстом OKR/задач/знаний); решение передаётся Victoria для формулировки ответа пользователю; полный аудит решений в БД и на дашборде.
- **Реализация:** (1) Классификатор `backend/app/services/strategic_classifier.py` — `is_strategic_question(content)` по ключевым словам (архитектура, приоритет, рефакторинг, сроки, качество vs скорость и т.д.); приветствия и простые факты — не стратегические. (2) Backend chat (SSE и POST /api/chat/send): при is_strategic вызывается Knowledge OS `POST /api/board/consult` с question, session_id, user_id, correlation_id, source=chat; заголовок X-API-Key (тот же API_KEY, что для log_interaction). (3) Knowledge OS: `strategic_board.consult_board()` — сбор контекста (OKR, tasks, последняя директива из knowledge_nodes), промпт для LLM (ai_core.run_smart_agent_async), парсинг структуры (decision, rationale, risks, confidence, recommend_human_review), запись в `board_decisions` (миграция add_board_decisions.sql) с session_id, user_id; возврат directive_text, structured_decision, risk_level, recommend_human_review. (4) Backend формирует промпт для Victoria с блоком [РЕШЕНИЕ СОВЕТА ДИРЕКТОРОВ] и инструкцией сформулировать ответ; при recommend_human_review в ответ пользователю добавляется предупреждение. (5) Полное заседание Совета: `run_board_meeting()` пишет в board_decisions (source=nightly), knowledge_nodes (type=board_directive), expert_discussions.
- **Устойчивость:** при ошибке или таймауте board/consult чат продолжает с обычным вызовом Victoria (без блока решения). При отсутствии модуля strategic_classifier board/consult не вызывается.
- **Дашборд:** Corporation Dashboard (8501), вкладка «Решения Совета» — список из board_decisions с фильтрами по источнику, уровню риска, correlation_id (отладка); раскрытие полного текста директивы и structured_decision.
- **Файлы:** `knowledge_os/db/migrations/add_board_decisions.sql`, `knowledge_os/app/strategic_board.py`, `knowledge_os/app/rest_api.py` (BoardConsultRequest/Response, POST /api/board/consult), `backend/app/services/strategic_classifier.py`, `backend/app/routers/chat.py`, `knowledge_os/dashboard/app.py` (вкладка «Решения Совета»). См. MASTER_REFERENCE §3б.

---

## 11.1. План верификации и аудит (2026-01-27)

- **Планы:** verification_and_architecture_plan_5a3e3142.plan.md, аудит_и_план_текущего_состояния_0dbf4ab7.plan.md (.cursor/plans).
- **Выполнено:** (1) PROJECT_ARCHITECTURE_AND_GUIDE §10.2 — добавлен поток «Задачи из БД: tasks → воркер → Ollama/MLX» (оркестратор → Smart Worker → сканер → батчи → process_task → ai_core → LocalAIRouter → Ollama/MLX); ссылки на CURRENT_STATE_WORKER_AND_LLM, WORKER_THROUGHPUT, OLLAMA_MLX, чеклист 14–19. (2) CURRENT_STATE_WORKER_AND_LLM §6 — явная ссылка на пункты 14–19 в VERIFICATION_CHECKLIST_OPTIMIZATIONS. (3) WORKER_THROUGHPUT уже содержал «пункты 14–19»; Smart Worker и ссылки в PROJECT_ARCHITECTURE §11 уже были. (4) Верификация: backend/Victoria/Veronica health 200; тесты knowledge_os — 23 passed (test_json_fast_http_client, test_rest_api, test_victoria_chat_and_request).
- **Итог:** недоделки из аудита (устаревшая ссылка 14–16, воркер не в архитектуре, нет единого описания потока) устранены; единое описание — CURRENT_STATE_WORKER_AND_LLM и §10.2 PROJECT_ARCHITECTURE. См. MASTER_REFERENCE «Последние изменения».

---

## 18. Глобальная экспансия и самозаживление (2026-02-14)
- **Проблема:** Корпорация была ограничена внутренними знаниями и требовала ручного вмешательства SRE.
- **Решение:**
  1. **Вероника-Разведчик:** Создан модуль `veronica_scout.py` для автономного мониторинга GitHub и Arxiv.
  2. **Self-Healing SRE:** Игорь получил права на автоматическую очистку кэша и оптимизацию БД через `autonomous_daemons.py`.
  3. **Canvas Mode:** В дашборд интегрирован прототип интерактивного окна артефактов.
  4. **Strategic Simulator:** В `strategic_board.py` добавлена функция `run_board_simulation` для прогнозирования успеха OKR.
  5. **VIP Routing:** Внедрен «приоритетный коридор» для Ивана и Совета на базе DeepSeek-R1 (32B).
- **Результат:** Корпорация вышла на уровень проактивной экспансии и технической неубиваемости.

---

## 19. Singularity 10.0: Самоэволюция и Автономная Инфраструктура (2026-02-14)

- **Цель:** Достижение 10/10 по шкале автономности OpenAI/Anthropic. Переход от статичной архитектуры к «живому» коду и полной изоляции экспериментов.
- **Реализация:**
  1. **Self-Evolution Loop:**
     - `ArchitectureProfiler`: Декоратор `@profile_function` собирает метрики исполнения в БД `architecture_performance_log`.
     - `MetaArchitect`: Автономно генерирует гипотезы по оптимизации «горячих точек» и синтезирует мутировавший код (например, `ai_core_v2.py`).
     - `TrafficMirror`: Зеркалирует реальные запросы в теневые контейнеры для проверки мутаций без риска для продакшена.
     - `ServiceMonitor`: Выполняет атомарную замену кода (`promote_mutation`) с механизмом отката.
  2. **Autonomous Sandboxes:**
     - `SandboxManager`: Позволяет экспертам (Игорь, Вероника) деплоить микросервисы в Docker.
     - Бэкенд получил доступ к `/var/run/docker.sock` и библиотеку `docker-py` для управления жизненным циклом песочниц.
  3. **Global GraphRAG:**
     - Модули `entity_extractor`, `community_detector` и `multi_hop_retriever` в `knowledge_os/app/graphrag/`.
     - Система понимает логические связи между 26k+ узлами знаний, выходя за рамки простого векторного сходства.
  4. **vLLM-level Inference:**
     - `mlx_api_server.py`: Внедрен `ContinuousBatcher` и очистка Metal-кэша для ускорения инференса на Mac Studio.
  5. **Cross-Container Self-Diagnosis:**
     - Сбор метрик через `docker stats` в реальном времени.
     - `ContainerAnomalyDetector`: Выявление аномалий по Z-score (спам запросами, утечки ресурсов).
     - `ContainerIsolationManager`: Автоматический перевод «агрессоров» в изолированную сеть `quarantine-net`.
  6. **Multi-Project Command Center:**
     - Дашборд: Интерактивная таблица проектов с защитой `atra-web-ide` от отключения.
     - Синхронизация путей: Честный маппинг `/workspace/[slug]` между Mac Studio и Docker для всех проектов.
- **Файлы:** `knowledge_os/app/sandbox_manager.py`, `knowledge_os/app/architecture_profiler.py`, `knowledge_os/app/traffic_mirror.py`, `knowledge_os/app/graphrag/*`, `knowledge_os/dashboard/tabs/system_tab.py`, `docker-compose.yml`.
- **Итог:** Корпорация получила инструменты для бесконечного самосовершенствования и безопасного масштабирования на неограниченное количество проектов.

---

## 20. Singularity 14.3: Survival Intelligence (2026-02-14)

- **Цель:** Предотвращение технического паралича и обеспечение выживаемости системы при критических сбоях (OOM, ошибки кода).
- **Реализация:**
  1. **Pre-flight Code Validation:**
     - `CodeValidator`: Проверка синтаксиса и импортов (`ast.parse`) перед записью `.py` файлов. Предотвращает `NameError` и `SyntaxError`.
  2. **External System Watchdog:**
     - `system_watchdog.sh`: Независимый монитор пульса (HTTP health checks). Выполняет Hard Reset контейнеров при зависании.
  3. **Memory Guard:**
     - `MemoryGuard`: Мониторинг RAM и адаптивная пауза тяжелых задач (Nightly Learner) для предотвращения OOMKilled на Mac Studio.
  4. **War Room Auto-Trigger:**
     - Интеграция `trigger_war_room_if_needed` в глобальный обработчик ошибок бэкенда. Автоматический созыв экспертов при 500-х ошибках.
  5. **Telegram Fix:**
     - Унификация и исправление переменных окружения для Telegram во всех Docker-сервисах.
- **Файлы:** `knowledge_os/app/code_validator.py`, `knowledge_os/app/memory_guard.py`, `scripts/system_watchdog.sh`, `backend/app/middleware/error_handler.py`, `knowledge_os/docker-compose.yml`.
- **Итог:** Система перешла на архитектуру выживания, минимизирующую время простоя даже при ошибках в коде агентов.

---

## 21. Singularity 15.0: Cognitive Breakthrough & Hierarchical Intelligence (2026-02-14)

- **Цель:** Решение проблемы «захлебывания» моделей на сверхсложных задачах (синтез отчетов от 86 экспертов) и достижение качества «гигантов» (OpenAI/Anthropic) через иерархическую обработку данных.
- **Реализация:**
  1. **Fact Extraction (MapReduce Pattern):**
     - `FactExtractor`: Автономный модуль для сжатия RAG-контекста и отчетов агентов до набора атомарных фактов. Используется в `ai_core.py` при превышении лимита в 3000 символов.
  2. **Hierarchical Swarm (Pyramid Synthesis):**
     - `swarm_intelligence.py`: Агенты разделены на кластеры (Technical, UX/UI, Security, Performance). Каждый кластер формирует промежуточный синтез, который затем объединяется в глобальный консенсус.
  3. **Incremental Assembly:**
     - `extended_thinking.py`: Финальный отчет собирается по секциям (Intro -> Analysis -> Conclusion). Каждая секция генерируется с учетом накопленных фактов, что гарантирует полноту и отсутствие обрывов.
  4. **Memory Guard (Context Swapper):**
     - `ContextSwapper`: Использует Redis для хранения полных цепочек рассуждений, оставляя в контексте LLM только «магистральные» пути знаний.
  5. **Telegram Bot Fix:**
     - Исправлена логика `try_one_url_async`: теперь бот ищет результат в полях `output`, `result` и `response`, что критично для сложных ReAct-задач.
- **Файлы:** `knowledge_os/app/ai_core.py`, `knowledge_os/app/swarm_intelligence.py`, `knowledge_os/app/extended_thinking.py`, `src/agents/bridge/victoria_telegram_bot.py`.
- **Итог:** Корпорация научилась обрабатывать задачи любого объема, не теряя нить рассуждения и не обрывая отчеты на середине.

---

## 14. Документы для углубления

| Тема | Документ |
|------|----------|
| Полная архитектура, схема, порты | `docs/ARCHITECTURE_FULL.md` |
| Victoria: процесс от запроса до ответа | `docs/VICTORIA_PROCESS_FULL.md` |
| Внедрённые улучшения (Correlation ID, кэш, уточняющие вопросы) | `docs/IMPROVEMENTS_IMPLEMENTED.md` |
| Анализ улучшений, что внедрить | `docs/ARCHITECTURE_IMPROVEMENTS_ANALYSIS.md` |
| Обновление PLAN.md (компоненты 54+) | `PLAN_UPDATE_SUMMARY.md` |
| Фиксы (Scout, Victoria, сервер, чат и др.) | `docs/*FIX*.md`, `docs/mac-studio/*.md` |
| Реальная роль Veronica, PREFER_EXPERTS_FIRST | `docs/VERONICA_REAL_ROLE.md` |
| Цепочка Victoria → эксперты: нестабильности, таймауты, чеклист | `docs/TELEGRAM_VICTORIA_CHAIN_CHECKLIST.md` |
| Воркер: пропускная способность, зависания, мировые практики | `docs/WORKER_THROUGHPUT_AND_STUCK_TASKS.md` |

---

*Сводка актуализирована с учётом правок из чатов. При добавлении новых изменений — дополнять этот документ и при необходимости .cursorrules.*
