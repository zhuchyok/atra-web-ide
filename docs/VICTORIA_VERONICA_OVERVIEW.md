# Victoria и Veronica: обзор и изменения

Краткая сводка по агентам Victoria и Veronica с учётом текущей архитектуры и новых изменений (2026-01-31).

**Вся архитектура проекта (структура, порты, запуск, API, метрики, Cursor, команда):** **`docs/PROJECT_ARCHITECTURE_AND_GUIDE.md`**.

---

## Кто такие

| Агент    | Роль           | Порт | Контейнер        | Где запускается                |
|----------|----------------|------|------------------|---------------------------------|
| **Victoria** | Team Lead, координатор | **8010** | victoria-agent   | knowledge_os/docker-compose.yml |
| **Veronica** | Local Developer, исполнитель | **8011** | veronica-agent   | knowledge_os/docker-compose.yml |

Оба агента **общие для всех проектов** (atra-web-ide, atra и др.). Контекст проекта передаётся в запросах через `project_context`; основной проект: `MAIN_PROJECT=atra-web-ide`.

---

## Цепочка запроса

1. Пользователь → **Web IDE backend (8080)** → `POST /api/chat/stream` или `POST /api/chat/plan`.
2. Backend ограничивает число одновременных запросов к Victoria (**MAX_CONCURRENT_VICTORIA=50**). При перегрузке возвращает **503** с `Retry-After: 60`.
3. Backend → **Victoria (8010)**. Victoria при необходимости делегирует задачи в **Veronica (8011)** или в отделы/оркестратор БД.
4. Ответ возвращается пользователю (SSE или JSON).

Подробная схема: `docs/ARCHITECTURE_FULL.md`. Процесс Victoria: `docs/VICTORIA_PROCESS_FULL.md`.

---

## Новые изменения (учтены в VICTORIA.md, VERONICA.md, .cursorrules)

- **Ограничение нагрузки на Victoria:** семафор в backend (по умолчанию 50 слотов). При перегрузке — 503 вместо 500. Настройка: `MAX_CONCURRENT_VICTORIA`, `VICTORIA_CONCURRENT_WAIT_SEC` (config.py / .env).
- **Стресс-тест:** Locust в venv (`./scripts/load_test/setup_venv.sh`), затем `RUN_TIME=1m USERS=30 SPAWN_RATE=5 ./scripts/run_load_test.sh`. Отчёт: `scripts/load_test/out/load_test_report.html`. Подробно: `docs/LOAD_TEST_RESULTS.md`, `docs/REPORT_STRESS_AND_METRICS.md`.
- **Метрики:** Prometheus (backend: 9091, Knowledge OS: 9092), Grafana (Web IDE: 3002, Knowledge OS: 3001). Эндпоинты backend: `/metrics`, `/metrics/summary`.
- **Redis:** Web IDE использует **knowledge_redis** из Knowledge OS (REDIS_URL в backend), отдельный контейнер atra-redis не нужен.
- **Cursor: роли и команда:** Роли в `.cursor/rules/` (01–21), индекс — `.cursor/README.md`. Соответствие экспертов (Виктория, Игорь, Анна, Елена и др.) правилам — `configs/experts/team.md`. Контекст Victoria/Veronica для Cursor: `VICTORIA.md`, `VERONICA.md`.

---

## Порядок запуска

1. `docker-compose -f knowledge_os/docker-compose.yml up -d` (Victoria, Veronica, БД, Redis, Prometheus и др.)
2. `docker-compose up -d` (Web IDE: backend, frontend, Prometheus, Grafana)

Проверка backend: `curl -s http://localhost:8080/health`. Проверка Victoria: `GET http://localhost:8010/status` (в ответе `victoria_levels`: agent, enhanced, initiative).

---

## Документы

- **docs/PROJECT_ARCHITECTURE_AND_GUIDE.md** — архитектура проекта: структура, компоненты, порты, запуск, API, метрики, стресс-тест, Cursor, команда (единая точка входа по проекту).
- **VICTORIA.md** — контекст Victoria: порты, команда, Cursor-роли, лимиты, стресс-тест, контекстные файлы.
- **VERONICA.md** — контекст Veronica: порты, связь с Victoria и backend, правила, контекстные файлы.
- **.cursorrules** — компоненты, API, порядок запуска, Cursor (роли, команда), конфигурация Victoria/Veronica.
- **docs/ARCHITECTURE_FULL.md** — полная схема Victoria → делегирование → Veronica.
- **docs/VICTORIA_PROCESS_FULL.md** — процесс от запроса до выполнения задачи.
