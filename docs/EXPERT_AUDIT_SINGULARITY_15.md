# Аудит Singularity 15.0 (эксперты Игорь, Анна, Сергей, Елена)

**Дата:** 2026-02-14  
**Область:** ask_victoria, Open WebUI tool, Victoria stream, Telegram LTM, метрики.

## Выявленные недостатки и исправления

### Backend (Игорь)

- **Валидация goal:** После `strip()` пустая или только-пробельная строка уходила в Victoria. Добавлена проверка: при пустом `goal_stripped` возврат **422** и сообщение «goal is required and cannot be empty».
- **Лимит нагрузки:** `/ask-victoria` не использовал семафор Victoria — при наплыве запросов можно было перегрузить агента. Добавлены `acquire_victoria_slot` / `release_victoria_slot` в `try/finally`; при отказе — **503** и заголовок **Retry-After: 60**.
- **Тест:** Добавлен `test_ask_victoria_empty_goal_422` (goal из пробелов → 422).

### QA (Анна)

- **Граничный случай в стриме Victoria:** При `TaskResponse(output=None)` переменная `full_response_content` становилась `None`, что ломало `outcome_summary=full_response_content[:200]` и итерацию по чанкам. Во всех ветках задаётся строка: `(result.output or "")`, `(result.output or "")`, `str(result) if result is not None else ""`, и при сохранении в LTM — `(full_response_content or "")[:200]`.
- **Тесты:** 6 тестов для ask-victoria (успех plain/json, 503, уточнения, user_key, 422 при пустом goal). Все проходят.

### DevOps / конфиг (Сергей)

- **Скрипт `openwebui_ask_victoria.py`:** Логика DEFAULT_URL перезатирала явно заданный `VICTORIA_URL` (например `http://192.168.1.5:8010`), подставляя `http://localhost:8010`. Исправлено: используется только `os.getenv("VICTORIA_URL") or "http://victoria-agent:8000"`; при запуске с хоста нужно задать `VICTORIA_URL=http://localhost:8010`.

### SRE / метрики (Елена)

- **Метрика ask_victoria:** Добавлен счётчик **ASK_VICTORIA_TOTAL** с лейблом `status` (success | error | busy). В endpoint при успехе/ошибке/перегрузке вызывается `ASK_VICTORIA_TOTAL.labels(status=...).inc()`.
- **Сводка:** В **GET /metrics/summary** добавлен блок **ask_victoria_total** (по статусам success, error, busy) для дашбордов и алертов.

## Итог

- Валидация и лимит нагрузки на `/ask-victoria` приведены в порядок.
- Стрим Victoria не падает при `output=None`.
- Скрипт не перезатирает `VICTORIA_URL`.
- Метрики и сводка дают наблюдаемость по ask_victoria.

**Рекомендация:** В Grafana добавить панель по `ask_victoria_total{status=...}` и алерт при росте `error` или `busy`.
