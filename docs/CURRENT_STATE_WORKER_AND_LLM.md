# Текущее состояние: воркер и LLM (Ollama/MLX)

Единый документ о том, как сейчас устроены обработка задач воркером и подключение к LLM (Ollama, MLX). Для верификации и разработки.

**Связанные документы:** [WORKER_THROUGHPUT_AND_STUCK_TASKS.md](WORKER_THROUGHPUT_AND_STUCK_TASKS.md), [OLLAMA_MLX_CONNECTION_AND_ECHO.md](OLLAMA_MLX_CONNECTION_AND_ECHO.md), [ARCHITECTURE_FULL.md](ARCHITECTURE_FULL.md), [MASTER_REFERENCE.md](MASTER_REFERENCE.md).

---

## 1. Поток задач воркера

1. **Enhanced Orchestrator** (фоновый цикл) читает из БД задачи с `assignee_expert_id IS NULL`, назначает эксперта (`assignee_expert_id`), обновляет задачу.
2. **Smart Worker** (`knowledge_os/app/smart_worker_autonomous.py`) в главном цикле:
   - Сбрасывает зависшие: задачи в `in_progress` с `updated_at` старше **SMART_WORKER_STUCK_MINUTES** (по умолчанию 15) возвращаются в `pending`.
   - Выбирает pending-задачи с назначенным экспертом (JOIN experts), до **SMART_WORKER_BATCH_SIZE** (по умолчанию 50), лимит по семафору **SMART_WORKER_MAX_CONCURRENT** (по умолчанию 10).
   - При **SMART_WORKER_BATCH_BY_MODEL=true**: сканирует доступные модели (Ollama/MLX), назначает каждой задаче **preferred_model** по категории и **preferred_source** (mlx/ollama), группирует по **(preferred_source, preferred_model)**; при **SMART_WORKER_INTERLEAVE_BLOCKS=true** (по умолчанию) очередь формируется чередованием блоков, чтобы MLX и Ollama обрабатывали задачи одновременно.
   - **Сколько задач берутся в работу одновременно:** при **SMART_WORKER_ADAPTIVE_CONCURRENCY=false** (по умолчанию) — фиксированный **SMART_WORKER_MAX_CONCURRENT** (10). При **SMART_WORKER_ADAPTIVE_CONCURRENCY=true** воркер считает **effective_N** по CPU/памяти хоста и загрузке MLX/Ollama (модуль `adaptive_concurrency`, кэш 15 сек); семафор использует `min(effective_N, MAX_CONCURRENT)`. Пул БД создаётся по потолку `max(15, MAX_CONCURRENT + 8)`, чтобы хватало при любом effective_N. Подробно: [ADAPTIVE_WORKER_CONCURRENCY_PLAN.md](ADAPTIVE_WORKER_CONCURRENCY_PLAN.md).
   - Запускает обработку через **семафор**: как только одна задача завершилась, сразу стартует следующая из списка (не ждёт весь батч).
3. **process_task** для каждой задачи:
   - Переводит задачу в `in_progress`, запускает **heartbeat** (каждые 15 сек обновляет `updated_at` в БД).
   - Обогащение контекста файлами: вызов **file_context_enricher** через **run_in_executor** (чтобы не блокировать event loop).
   - Для источников `dashboard_scout` / `dashboard_simulator` — вызов scout_task_processor / simulator; иначе — вызов **run_cursor_agent_smart** → **ai_core.run_smart_agent_async** с таймаутом 300 сек.
   - При батчах по модели выставляет в роутере **preferred_source** и **preferred_model** (переиспользуемый роутер, см. ниже).
   - По завершении — валидатор результата, затем `completed` или `failed` (при ошибке задача возвращается в `pending`).

---

## 2. URL Ollama и MLX

| Место | Переменные | Поведение |
|-------|------------|-----------|
| **LocalAIRouter** (`knowledge_os/app/local_router.py`) | `OLLAMA_API_URL`, `OLLAMA_BASE_URL`, `MLX_API_URL` | Формирует `self.nodes`; если не заданы — в Docker `host.docker.internal`, локально `localhost`. |
| **Воркер (батчи по модели)** | `MLX_API_URL`, `OLLAMA_API_URL`, `OLLAMA_BASE_URL` | Сканер `get_available_models(mlx_url, ollama_url)`; в Docker fallback `host.docker.internal`. |
| **available_models_scanner** | env в `_default_ollama_url()` / `_default_mlx_url()` | При вызове без аргументов — env + логика Docker. |

Итог: везде URL берутся из env с fallback на `host.docker.internal` (Docker) или `localhost`. Неверный или не заданный URL → таймауты, пустые ответы.

---

## 3. Распределение задач по блокам (источник + модель)

**Оркестратор vs воркер:** оркестратор назначает **preferred_source** (mlx/ollama) в metadata при assign_task_to_best_expert по отделу эксперта (ML/Backend/R&D/Performance → mlx; остальные → ollama). Воркер использует preferred_source из metadata; если нет — fallback по intelligent_model_router. Модель — из сканера по категории. Если оркестратор решил, что нужна тяжёлая — приоритеты в сканере это учитывают.

**Не «предпочтения»:** задачи **распределяются по блокам** (источник + модель). Модель выбирается по **доступности** (сканер) и по **типу задачи**.

1. **Сканер** (`available_models_scanner`): вызывает **get_available_models(mlx_url, ollama_url)** (кэш 120 сек). Список моделей MLX и Ollama — раздельно; для каждой задачи по категории (reasoning/coding/fast/default) выбирается модель через **pick_mlx_for_category** / **pick_ollama_for_category** из **актуальных** моделей в сканере.
2. **Оркестратор / Victoria:** назначение эксперта, категория задачи; воркер использует **intelligent_model_router** (оценка сложности) или fallback по bug_probability, чтобы отнести задачу к источнику **mlx** или **ollama**.
3. **Блоки:** задачи группируются по **(preferred_source, preferred_model)**. В **process_task** воркер передаёт в ai_core роутер с `_preferred_source` и `_preferred_model`.
4. **Время загрузки модели:** при смене модели (новый блок) Ollama/MLX могут загружать модель при первом запросе (30–90 сек для тяжёлых). **Нужно учитывать** время загрузки и запас на развёртывание перед отправкой задач; иначе — ReadTimeout, зависание. MLX ждёт загрузки (_loading_models); Ollama — загрузка ленивая, буфер не учтён. См. VERIFICATION_CHECKLIST_OPTIMIZATIONS.md, раздел 3.

---

## 3.1. Одновременная обработка в Ollama и MLX (чередование блоков)

- **Цель:** обрабатывать задачи **и в MLX, и в Ollama одновременно**; **тяжёлый/лёгкий pairing** — когда Ollama тяжёлая, MLX лёгкая, и наоборот (ADAPTIVE_WORKER_CONCURRENCY_PLAN).
- **Распределение:** при **SMART_WORKER_HEAVY_LIGHT_PAIRING=true** (по умолчанию) — 50/50 round-robin по источникам (чётная задача → MLX, нечётная → Ollama). Модель — из сканера по категории. Блоки упорядочиваются: (mlx/heavy, ollama/light), (mlx/light, ollama/heavy) — чтобы не грузить оба бэкенда тяжёлыми. При false — intelligent_model_router по сложности.
- **Чередование:** при **SMART_WORKER_INTERLEAVE_BLOCKS=true** очередь формируется чередованием блоков; при pairing — тяжёлый на одном, лёгкий на другом.
- **Без чередования** (SMART_WORKER_INTERLEAVE_BLOCKS=false): очередь как раньше — сначала все задачи самого большого блока, затем следующего; MLX может долго простаивать, пока не опустеет блок Ollama.
- **LocalAIRouter:** держит оба узла (MLX 11435, Ollama 11434); одна задача → один бэкенд (тот, что назначен для блока). Много задач → параллельно по семафору, при чередовании — и там и там идёт обработка.
- При перегрузке MLX роутер ставит Ollama первым для следующего запроса.

---

## 4. Защита от эхо-ответа

- В **local_router.run_local_llm** после получения ответа вызывается **\_is_echo_response(result, prompt)**.
- Эхо считается, если: (1) ответ и промпт совпадают (после strip), или (2) ответ короткий (**len(r) < 200** после исправления регрессии) и промпт начинается с ответа или ответ начинается с промпта — чтобы снизить ложные срабатывания на короткие легитимные ответы («Да», «Готово»).
- При срабатывании — логируем предупреждение, переходим к следующему узлу (Ollama/MLX) или возвращаем `None`.

---

## 5. Восстановление при сбоях

- **system_auto_recovery.sh** (launchd, каждые 5 мин): Wi‑Fi, интернет, Docker, сеть atra-network, Knowledge OS docker-compose up -d, Web IDE docker-compose up -d, MLX API Server (порт 11435), Ollama (11434), проверка Victoria (:8010/status), Veronica (:8011), сводка.
- **check_and_start_containers.sh**: ручная проверка и запуск контейнеров; при выключенных Enhanced/Initiative — перезапуск victoria-agent.
- Зависшие задачи: сброс в **pending** через **SMART_WORKER_STUCK_MINUTES** (15 мин) в главном цикле воркера и при взятии задачи.

---

## 6. Что проверять

Полный чеклист верификации воркера и Ollama/MLX: **пункты 14–19** в [VERIFICATION_CHECKLIST_OPTIMIZATIONS.md](VERIFICATION_CHECKLIST_OPTIMIZATIONS.md) (пул БД, run_in_executor, URL из env, эхо, батчи по модели, делегирование Victoria/Veronica, чат с Victoria).

- [ ] Воркер: логи «Found N pending tasks», «Батчи по модели: M блоков», «Completed: N tasks processed»; в БД — рост `completed`, уменьшение `pending`/`in_progress` при отсутствии новых поступлений.
- [ ] Heartbeat: без частых «Heartbeat error» в логах; зависшие сбрасываются с сообщением «Вернуто в очередь зависших задач (>15 мин): N».
- [ ] Ollama/MLX: в контейнере воркера заданы `OLLAMA_API_URL` и `MLX_API_URL` (при необходимости `http://host.docker.internal:11434/11435`); после изменений — перезапуск контейнера knowledge_os_worker.
- [ ] **MLX не используется:** если в Activity Monitor видна только работа Ollama — см. [MLX_TASK_PROCESSING_CHECK.md](MLX_TASK_PROCESSING_CHECK.md): MLX API Server (порт 11435) должен быть запущен на хосте (`scripts/start_mlx_api_server.sh`); в логах при отсутствии MLX раз в 5 мин появляется предупреждение роутера.
- [ ] Эхо: при жалобах на «нет ответа» или смену узла без причины — проверить логи «Эхо-ответ от …» и при необходимости ослабить условие в _is_echo_response.

---

*Документ актуализирован при внесении изменений в воркер или LLM-цепочку. Все новые правки отражать здесь и в [MASTER_REFERENCE.md](MASTER_REFERENCE.md).*
