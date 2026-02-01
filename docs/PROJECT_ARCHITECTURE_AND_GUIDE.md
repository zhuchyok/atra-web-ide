# Архитектура проекта ATRA Web IDE и руководство

Единый документ: структура проекта, компоненты, порты, запуск, API, метрики, стресс-тест, Cursor и команда экспертов. Детальная схема Victoria → Veronica и оркестрация: **`docs/ARCHITECTURE_FULL.md`**.

**Обновлено:** 2026-01-31

---

## 1. Проект

- **Название:** ATRA Web IDE  
- **Назначение:** браузерная оболочка для ИИ-корпорации Singularity 9.0 (чат с Victoria/Veronica, редактор кода, файлы, превью).  
- **Контекст:** основной проект корпорации — `MAIN_PROJECT=atra-web-ide`; агенты Victoria и Veronica общие для всех проектов (atra, atra-web-ide и др.), контекст передаётся через `project_context` в запросах.

---

## 2. Структура проекта

```
atra-web-ide/
├── backend/                 # FastAPI (порт 8080)
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routers/         # chat, files, experts, preview, plan_cache, metrics, ab_testing
│   │   ├── services/        # victoria, rag_light, plan_cache, concurrency_limiter
│   │   └── metrics/
│   └── requirements.txt
├── frontend/                # Svelte + Tailwind (порт 3000)
├── knowledge_os/            # Knowledge OS (оркестратор, БД, агенты)
│   ├── docker-compose.yml   # Victoria 8010, Veronica 8011, Prometheus 9092, Grafana 3001
│   ├── app/                 # victoria_enhanced, task_delegation, enhanced_orchestrator
│   └── ...
├── src/
│   └── agents/bridge/      # victoria_server.py, victoria_telegram_bot.py
├── .cursor/                 # Настройки Cursor
│   ├── README.md            # Индекс ролей и связь с командой
│   ├── rules/               # 01–21 роли (Quant, Backend, QA, ML, SRE, Security, Tech Writer и др.)
│   ├── prompts/
│   ├── commands/
│   └── workflows/
├── configs/
│   └── experts/
│       ├── team.md          # Основные роли и соответствие .cursor/rules
│       ├── employees.json   # Единый источник списка сотрудников (имя, роль, отдел)
│       ├── employees.md     # Таблица сотрудников (генерируется из employees.json)
│       └── _known_names_generated.py  # KNOWN_EXPERT_NAMES (генерируется sync_employees.py)
├── scripts/
│   ├── run_load_test.sh     # Стресс-тест (Locust)
│   ├── run_full_load_test.sh
│   └── load_test/           # locustfile.py, setup_venv.sh, out/
├── docs/                    # Документация
├── prometheus/              # Конфиг Prometheus Web IDE (порт 9091)
├── grafana/                 # Дашборды Web IDE (порт 3002)
├── docker-compose.yml       # Web IDE: backend, frontend, Prometheus, Grafana
├── .cursorrules             # Правила Cursor (компоненты, API, запуск, Cursor-роли)
├── VICTORIA.md              # Контекст Victoria
├── VERONICA.md              # Контекст Veronica
├── PLAN.md
└── README.md
```

---

## 3. Компоненты и порты

| Компонент | Порт (хост) | Описание |
|-----------|-------------|----------|
| **Frontend** | 3000 | Svelte, чат, редактор, файлы. |
| **Backend** | 8080 | FastAPI: чат/stream, plan, RAG, план-кэш, метрики, A/B. Ограничивает число запросов к Victoria (семафор). |
| **Victoria** | 8010 | Team Lead, один сервис (victoria-agent). Три уровня: Agent, Enhanced, Initiative. Запуск: knowledge_os/docker-compose.yml. |
| **Veronica** | 8011 | Local Developer (veronica-agent). Вызывается Victoria при делегировании. |
| **PostgreSQL** | 5432 | knowledge_postgres, БД knowledge_os (experts, tasks и др.). |
| **Redis** | 6379 (в сети) | knowledge_redis из Knowledge OS. Web IDE использует его (REDIS_URL), отдельный atra-redis не нужен. |
| **Prometheus (Web IDE)** | 9091 | Метрики backend. |
| **Grafana (Web IDE)** | 3002 | Дашборды (логин admin/admin). |
| **Prometheus (Knowledge OS)** | 9092 | Метрики Knowledge OS (если 9090 занят). |
| **Grafana (Knowledge OS)** | 3001 | Дашборды Knowledge OS. |
| **Ollama** | 11434 | LLM на хосте. |
| **MLX API** | 11435 | LLM на хосте. |

---

## 4. Порядок запуска

1. **Knowledge OS** (Victoria, Veronica, БД, Redis, Prometheus, Grafana и др.):
   ```bash
   docker-compose -f knowledge_os/docker-compose.yml up -d
   ```
   Подождать 15–20 сек.

2. **Web IDE** (backend, frontend, Prometheus, Grafana):
   ```bash
   docker-compose up -d
   ```

3. **Проверка:**
   - Backend: `curl -s http://localhost:8080/health`
   - Victoria: `curl -s http://localhost:8010/status` (в ответе `victoria_levels`: agent, enhanced, initiative)
   - Frontend: http://localhost:3000
   - **Victoria Telegram Bot** (процесс на хосте, не в Docker): `pgrep -f victoria_telegram_bot` — если пусто, запустить: `cd /path/to/atra-web-ide && python3 -m src.agents.bridge.victoria_telegram_bot`. Автозапуск при загрузке: `bash scripts/setup_victoria_telegram_bot_autostart.sh`. Подробнее: `docs/TELEGRAM_VICTORIA_TROUBLESHOOTING.md`.

Если backend недоступен — сначала поднять Knowledge OS (сеть atra-network и сервисы).

---

## 5. API (Backend)

| Метод | Путь | Описание |
|-------|------|----------|
| GET | /health | Состояние backend и зависимостей (Victoria, Ollama, MLX). |
| POST | /api/chat/stream | Чат (SSE). Запросы к Victoria; при перегрузке — 503 с Retry-After. |
| POST | /api/chat/plan | План по цели (Victoria). |
| GET | /metrics | Метрики в формате Prometheus. |
| GET | /metrics/summary | Краткая сводка метрик. |
| GET | /api/files | Список файлов. |
| GET | /api/experts | Список экспертов. |
| GET | /api/preview | Превью файлов. |
| POST | /api/plan-cache/clear | Очистка кэша планов. |
| POST | /api/rag-optimization/cache/clear | Очистка кэша RAG. |
| GET | /api/ab-testing/experiments | A/B-эксперименты. |
| GET | /api/ab-testing/user/{user_id}/variants | Варианты пользователя. |

---

## 6. Ограничение нагрузки на Victoria

- Backend ограничивает число одновременных запросов к Victoria (семафор).
- По умолчанию: **MAX_CONCURRENT_VICTORIA=50** (`backend/app/config.py`).
- **VICTORIA_CONCURRENT_WAIT_SEC** — время ожидания слота (сек), затем 503.
- При перегрузке клиент получает **503 Service Unavailable** с заголовком `Retry-After: 60` (вместо 500).
- Настройка: переменные в `.env` или config.py.

---

## 7. Метрики и стресс-тест

- **Метрики:** Prometheus (backend 9091), эндпоинты `/metrics`, `/metrics/summary`. Grafana Web IDE: http://localhost:3002.
- **Стресс-тест (Locust):**
  1. Один раз: `./scripts/load_test/setup_venv.sh`
  2. Запуск: `RUN_TIME=1m USERS=30 SPAWN_RATE=5 ./scripts/run_load_test.sh`
  3. Отчёт: `scripts/load_test/out/load_test_report.html`
- Подробно: `docs/LOAD_TEST_RESULTS.md`, `docs/REPORT_STRESS_AND_METRICS.md`.

---

## 8. Cursor: роли и команда

- **Роли (правила):** `.cursor/rules/` — файлы 01–21 (Quant, Trader, DevOps, Data Engineer, Risk, Data Scientist, System Architect, QA, Backend, ML, SRE, Security, Technical Writer, Financial Analyst, Frontend, UI/UX, Fullstack, SEO, Content, Legal, Code Reviewer). Индекс: **`.cursor/README.md`**.
- **Команда экспертов:** **`configs/experts/team.md`** — соответствие экспертов (Виктория, Игорь, Анна, Елена, Дмитрий, Алексей и др.) файлам в `.cursor/rules/`.
- **Полный список сотрудников:** единый источник **`configs/experts/employees.json`**. При добавлении нового сотрудника: добавьте запись в JSON, затем **`python scripts/sync_employees.py`** — обновятся seed, KNOWN_EXPERT_NAMES и таблица в employees.md.
- **Использование в промптах:** `@qa_engineer`, `@backend_developer`, `@ml_engineer`, `@sre_monitor`, `@security_engineer`, `@technical_writer` и др. (см. .cursor/README.md).
- **Контекст Victoria/Veronica для Cursor:** **`VICTORIA.md`**, **`VERONICA.md`**.

---

## 9. Конфигурация

- **.env** — переменные окружения (VICTORIA_URL, PROJECT_NAME, DATABASE_URL, REDIS_URL, MAX_CONCURRENT_VICTORIA и др.). Для Telegram-бота: TELEGRAM_BOT_TOKEN, TELEGRAM_USER_ID; при долгих задачах — VICTORIA_POLL_TIMEOUT_SEC (по умолчанию 900 сек = 15 мин).
- **docker-compose.yml** — Web IDE (backend, frontend, Prometheus, Grafana).
- **knowledge_os/docker-compose.yml** — Victoria, Veronica, БД, Redis, Prometheus, Grafana, оркестратор и др.
- **.cursorrules** — правила Cursor: компоненты, API, порядок запуска, Cursor-роли, конфигурация Victoria/Veronica.

---

## 10. Цепочка запроса (кратко)

1. Пользователь → **Frontend (3000)** или API → **Backend (8080)**.
2. Backend → семафор (лимит слотов Victoria) → при перегрузке 503.
3. Backend → **Victoria (8010)** (`POST /run` с goal, project_context).
4. Victoria решает: Department Heads (эксперты БД), делегирование **Veronica (8011)** или выполнение сама (ReAct, swarm).
5. Ответ возвращается пользователю (SSE или JSON).

Подробная схема и потоки: **`docs/ARCHITECTURE_FULL.md`**. Процесс Victoria от запроса до выполнения: **`docs/VICTORIA_PROCESS_FULL.md`**.

---

## 11. Связанные документы

| Документ | Содержание |
|----------|------------|
| **docs/ARCHITECTURE_FULL.md** | Полная схема Victoria → делегирование → Veronica, оркестратор, эксперты. |
| **docs/VICTORIA_PROCESS_FULL.md** | Процесс Victoria: от запроса до выполнения задачи. |
| **docs/VICTORIA_VERONICA_OVERVIEW.md** | Краткий обзор Victoria и Veronica, порты, изменения. |
| **VICTORIA.md** | Контекст Victoria: порты, команда, Cursor-роли, лимиты, стресс-тест. |
| **VERONICA.md** | Контекст Veronica: порты, связь с Victoria и backend. |
| **.cursorrules** | Компоненты, API, запуск, Cursor (роли, команда). |
| **.cursor/README.md** | Индекс ролей Cursor и связь с configs/experts/team.md. |
| **configs/experts/team.md** | Команда экспертов и соответствие .cursor/rules. |
| **configs/experts/employees.json** | Единый источник сотрудников. Новых — добавлять сюда, затем запускать `scripts/sync_employees.py`. |
| **configs/experts/employees.md** | Таблица сотрудников (генерируется из employees.json). |
| **docs/LOAD_TEST_RESULTS.md** | Стресс-тест: как запускать, результаты. |
| **docs/REPORT_STRESS_AND_METRICS.md** | Отчёт: метрики, стресс-тест, concurrency limiter. |
