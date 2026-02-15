# Mac Studio: характеристики, загрузка и настройки Victoria

**Назначение:** учитывать характеристики и загрузку Mac Studio при настройке Docker, Victoria, Veronica и бэкенда — чтобы система стабильно работала без вылетов и перегрузки.

**Связанные документы:** [VICTORIA_RESTARTS_CAUSE.md](VICTORIA_RESTARTS_CAUSE.md), [WORKER_THROUGHPUT_AND_STUCK_TASKS.md](WORKER_THROUGHPUT_AND_STUCK_TASKS.md), [MAC_STUDIO_M4_MODELS_GUIDE.md](MAC_STUDIO_M4_MODELS_GUIDE.md), [mac-studio/MAC_STUDIO_DOCKER_SETUP.md](mac-studio/MAC_STUDIO_DOCKER_SETUP.md).

---

## 1. Характеристики Mac Studio (ориентир)

| Параметр | Типично (M4 Max) |
|----------|-------------------|
| **Unified Memory** | 64 GB или 128 GB |
| **CPU** | 16 cores (12 performance + 4 efficiency) |
| **GPU** | 40 cores |
| **Neural Engine** | 16 cores |
| **Ollama** | на хосте, порт 11434 |
| **MLX API Server** | на хосте, порт 11435 |

- **Victoria и Veronica** работают **в Docker** (контейнеры), обращаются к Ollama/MLX по **host.docker.internal**.
- **Память:** Ollama и MLX загружают модели в **память хоста**. Контейнеры (Victoria, Veronica, Postgres, Redis, воркеры) используют память **Docker Desktop** (лимит в Settings → Resources → Memory). Итого: часть RAM — под Docker, часть — под хост (macOS + Ollama/MLX + модели).

### 1.1 Ollama: ограничение по размеру модели на Mac Studio

У **Ollama** нет жёсткого лимита на один буфер (как у Metal в MLX). Ограничение — **практическое по RAM**: объём модели в памяти не должен превышать доступную память хоста после вычета Docker и macOS.

| RAM Mac Studio | Docker (рекоменд.) | Доступно под модели (ориентир) | Рекомендуемый максимум одной модели Ollama | Примечание |
|----------------|--------------------|---------------------------------|--------------------------------------------|------------|
| **128 GB**     | 10–14 GB           | **до ~108 GB**                  | 70B (~40 GB) — ок; 104B (~60+ GB) — возможно, запас небольшой | Можно держать 3–4 модели одновременно (суммарно до ~108 GB). См. [MAC_STUDIO_M4_MODELS_GUIDE.md](MAC_STUDIO_M4_MODELS_GUIDE.md). |
| **64 GB**      | 10–12 GB           | **~38–42 GB**                   | 32B (~20 GB) — комфортно; 70B (~40 GB) — впритык | Тяжёлые 70B не держать вместе с большим числом других моделей; лучше 7B–32B. При 64 GB и 70B — один запрос за раз, таймауты увеличить. |

- **Ориентиры по объёму в RAM:** 7B ~4–14 GB, 32B ~20 GB, 70B ~40 GB, 104B ~60+ GB (зависит от квантизации).
- **Итог:** перед установкой тяжёлой модели в Ollama проверить общий RAM хоста и лимит Docker; сумма «Docker + macOS + приложения + модели» не должна вести к OOM. См. также §7 (меньше RAM).

### 1.2 Ollama: настройки приложения (Mac Studio)

В **Ollama → Settings** на Mac Studio рекомендуется:

| Настройка | Рекомендация | Пояснение |
|-----------|--------------|-----------|
| **Context length** | **32k** или **64k** | 4k слишком мало для кода и длинных диалогов. Модели (phi3.5, qwen2.5-coder и др.) поддерживают 32k–128k. 32k — баланс; 64k — при 64+ GB RAM; 128k — только при 128 GB и необходимости очень длинного контекста (больше памяти под KV-кэш). |
| **Model location** | По умолчанию `~/.ollama/models` | Менять только при нехватке места на системном диске. |
| **Expose to network** | Выключено | Достаточно localhost; из Docker — host.docker.internal:11434. |
| **Airplane mode** | По желанию | Выключено — для загрузки моделей; включить при строгой локальности. |

---

## 2. Рекомендуемые настройки Docker (Mac Studio)

- **Docker Desktop → Settings → Resources → Memory:**  
  **10–14 GB** для Mac Studio с 64–128 GB RAM. Так контейнерам хватает на старт Victoria/Veronica и воркеров с запасом, а большая часть памяти остаётся хосту для Ollama/MLX и тяжёлых моделей (32B ~20 GB, 70B ~40 GB). Раньше было 8–12 GB; немного увеличили, чтобы реже вылетал Docker при пиках.
- **Не ставить** лимит Docker ниже 8 GB при включённых Victoria Enhanced + Initiative и RAG preload — высок риск OOM при старте (см. VICTORIA_RESTARTS_CAUSE §2).
- **CPU:** можно оставить по умолчанию (половина ядер) или увеличить, если воркеры и агенты нагружают систему.

### 2.1 Docker вылетает — часто из‑за нехватки памяти

**Симптомы:** Docker Desktop закрывается, контейнеры падают, при следующем запуске «Cannot connect to the Docker daemon» или контейнеры в цикле рестартов (RestartCount растёт).

**Что проверить и сделать:**

1. **Лимит памяти Docker**  
   Docker Desktop → **Settings → Resources → Memory.** Для Mac Studio с 64–128 GB RAM ставь **10–14 GB** (минимум 8 GB). Если было 4–6 GB — увеличь до 10 GB и выше (при Victoria Enhanced + Initiative + RAG preload 4–8 GB часто не хватает → OOM → вылет).
2. **Проверка OOM после падения** (пока контейнер ещё есть):  
   `docker inspect victoria-agent --format '{{.State.OOMKilled}}'`  
   Если `true` — контейнер убит из‑за нехватки памяти.
3. **Если памяти мало** (машина с 32 GB или много всего запущено):  
   - Оставь Docker Memory **8 GB** и снизь нагрузку при старте Victoria: в `.env` или в `knowledge_os/docker-compose.yml` для `victoria-agent`:  
     `RAG_PRELOAD_TYPICAL_QUERIES=false`, `ENABLE_EVENT_MONITORING=false`, `SERVICE_MONITOR_ENABLED=false`  
   - Перезапуск: `docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent --force-recreate`.  
   Подробнее: [VICTORIA_RESTARTS_CAUSE.md](VICTORIA_RESTARTS_CAUSE.md) §2.
4. **Итого:** да, причина вылетов Docker нередко — нехватка памяти (чуть не хватило при пике). Увеличить лимит Docker и/или отключить часть предзагрузки и мониторинга.

---

## 3. Загрузка: кто что потребляет

| Компонент | Где работает | Память / нагрузка |
|-----------|--------------|--------------------|
| **Ollama** | хост (11434) | Модель в RAM хоста (phi 3.8B ~4 GB, qwen2.5-coder 32B ~20 GB, 70B ~40 GB). Один запрос — один вызов LLM. |
| **MLX API Server** | хост (11435) | Аналогично, модели в Unified Memory. Очередь запросов, батчи по модели (WORKER_THROUGHPUT). |
| **Victoria Agent** | Docker (8010) | Один воркер Uvicorn; при sync POST /run воркер занят до завершения задачи. Память контейнера: старт (skills, RAG preload, мониторинг) + пики при LLM. |
| **Veronica Agent** | Docker (8011) | Аналогично, запросы к Ollama/MLX через host.docker.internal. |
| **Backend (Web IDE)** | Docker (8080) | Ограничивает одновременные запросы к Victoria: **MAX_CONCURRENT_VICTORIA** (по умолчанию 50). При перегрузке — 503 + Retry-After. |
| **knowledge_os_worker** | Docker | До **SMART_WORKER_MAX_CONCURRENT** задач (по умолчанию 10); учёт загрузки Mac Studio через resource_monitor (RAM/CPU/temp), см. WORKER_THROUGHPUT. |

**Итог:** На Mac Studio одновременно могут идти запросы к Victoria (чат, план, /run), к Veronica, к воркеру и к Ollama/MLX. Чтобы не перегружать хост и не вызывать OOM или таймауты, важно ограничивать параллелизм и использовать **async_mode** для длинных задач Victoria.

---

## 4. Рекомендуемые переменные окружения (Mac Studio)

### 4.1 Backend (Web IDE)

| Переменная | Рекомендация для Mac Studio | Описание |
|------------|-----------------------------|----------|
| **MAX_CONCURRENT_VICTORIA** | `10`–`20` | Одновременных запросов к Victoria. 50 — много при одном Mac Studio (очередь в Ollama/MLX, один executor на задачу). Снижение уменьшает пики нагрузки. |
| **VICTORIA_TIMEOUT** | `900` | Таймаут ответа Victoria (сек). Для длинных задач лучше использовать async_mode и опрос /run/status. |
| **VICTORIA_URL** | `http://localhost:8010` | Локально на Mac Studio. В Docker — из compose. |

### 4.2 Victoria Agent (knowledge_os/docker-compose / .env)

| Переменная | Рекомендация для Mac Studio | Описание |
|------------|-----------------------------|----------|
| **USE_ELK** | `false` | Обязательно на Mac Studio (избежание падения при старте, VICTORIA_RESTARTS_CAUSE §3). |
| **OLLAMA_EXECUTOR_TIMEOUT** | `300` | Таймаут одного вызова LLM (сек). Тяжёлые модели на 32B/70B могут отвечать долго. |
| **VICTORIA_MAX_STEPS** | `500` (или меньше для чата) | Лимит шагов агента. Для чата бэкенд передаёт max_steps=50 (VICTORIA_MAX_STEPS_CHAT). |
| **RAG_PRELOAD_TYPICAL_QUERIES** | `true` | Ускоряет типовые запросы. При OOM или цикле рестартов временно `false` (VICTORIA_RESTARTS_CAUSE §2). |
| **ENABLE_EVENT_MONITORING** | `true` | Initiative (File Watcher, Service Monitor). При нехватке памяти можно временно `false`. |
| **UVICORN_WORKERS** | `1` | По умолчанию. Для /run/status и async_mode одного воркера достаточно; при workers>1 нужен общий store. |

### 4.3 Режим запросов к Victoria

- **Длинные задачи (список файлов, сложный анализ, много шагов):** использовать **async_mode**:  
  `POST /run?async_mode=true` → 202 + task_id → опрос `GET /run/status/{task_id}`.  
  Тогда воркер не блокируется на минуты, /health и опрос статуса отвечают. Скрипт: `scripts/run_victoria_tasks_3_and_4_async.sh`.
- **Короткие (привет, что умеешь, один факт):** можно sync POST /run без async_mode.

### 4.4 Время старта и загрузка моделей (запас)

- **Старт Victoria:** lifespan (skills, БД, эксперты, реестр проектов) обычно 25–40 с. Учтён запас: таймауты предзагрузки экспертов **30 с** (**VICTORIA_STARTUP_EXPERTS_TIMEOUT**), реестра **20 с** (**VICTORIA_STARTUP_REGISTRY_TIMEOUT**), запросы к БД **25 с** (**VICTORIA_DB_POOL_COMMAND_TIMEOUT**). На холодной БД или медленном диске можно увеличить через env.
- **У каждой модели своё время:** холодная загрузка в RAM и первый ответ сильно зависят от размера модели (1–4B: секунды; 32B: десятки секунд; 70B/104B: минуты). Ориентиры по размерам и рекомендуемые **OLLAMA_EXECUTOR_TIMEOUT**, **SERVICE_MONITOR_INITIAL_DELAY**, **VICTORIA_TIMEOUT** — в **[MODEL_TIMING_REFERENCE.md](MODEL_TIMING_REFERENCE.md)**.
- **Задержка перед первой проверкой мониторинга:** по умолчанию **50 с** (**SERVICE_MONITOR_INITIAL_DELAY**, диапазон 25–120). Этого хватает для лёгких/средних моделей; для 32B — лучше 60–75 с, для 70B/104B — 90–120 с и выше (см. таблицу в MODEL_TIMING_REFERENCE).

---

## 5. Проверка загрузки Mac Studio

- **Метрики хоста:** Backend GET `/api/system-metrics` (если включён) — CPU, память, диск. В Docker — метрики контейнера.
- **Victoria:** GET `http://localhost:8010/status` — эксперты, RAG, латентность; GET `/metrics` — Prometheus.
- **Ollama/MLX:** на хосте смотреть активность (Ollama UI или логи). При перегрузке MLX роутер может переключаться на Ollama (WORKER_THROUGHPUT § «Учёт загрузки Mac Studio»).
- **Контейнер Victoria:** при повторных рестартах — `docker inspect victoria-agent --format '{{.RestartCount}}'` и `{{.State.OOMKilled}}`; логи: `docker logs victoria-agent --tail 100`.

---

## 6. Краткий чек-лист под Mac Studio

1. **Docker Desktop:** Memory 8–12 GB (при 64–128 GB RAM хоста).
2. **USE_ELK=false** для victoria-agent.
3. **MAX_CONCURRENT_VICTORIA** в backend: 10–20 при одном Mac Studio.
4. Длинные задачи Victoria — через **async_mode** и опрос /run/status.
5. При OOM или цикле рестартов Victoria — временно отключить RAG_PRELOAD, EVENT_MONITORING или увеличить память Docker (VICTORIA_RESTARTS_CAUSE §2).
6. Модели Ollama/MLX — по MAC_STUDIO_M4_MODELS_GUIDE; тяжёлые 70B/104B учитывать при выборе лимитов и таймаутов.

---

## 7. Если железо слабее или меньше RAM (всё равно «как нужно», просто медленнее)

- **Меньше RAM (например 32–64 GB):** Docker 6–8 GB; **MAX_CONCURRENT_VICTORIA=10**; тяжёлые модели (70B) не держать вместе с Victoria — либо лёгкие модели (7B–32B), либо увеличить таймауты и не гонять много задач параллельно.
- **Медленнее:** те же настройки плюс **OLLAMA_EXECUTOR_TIMEOUT** и **VICTORIA_TIMEOUT** не уменьшать — пусть один запрос дольше, но не обрывается; для длинных сценариев обязательно **async_mode**, чтобы не блокировать воркер.
- **Цикл рестартов Victoria:** сразу включить «лёгкий старт» (VICTORIA_RESTARTS_CAUSE §2): RAG_PRELOAD_TYPICAL_QUERIES=false, ENABLE_EVENT_MONITORING=false, SERVICE_MONITOR_ENABLED=false; после стабилизации можно по одному вернуть.

Система рассчитана на то, чтобы стабильно работать и на более слабом оборудовании — просто с учётом лимитов и чуть больших задержек. Делаем всё как нужно; скорость подстраивается под железо.
