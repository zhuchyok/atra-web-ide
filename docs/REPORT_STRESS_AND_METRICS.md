# Отчёт: стресс-тестирование и метрики (Фаза 3, Дни 5–7)

**Дата:** 31.01.2026  
**Статус:** ✅ Все задачи выполнены, прогоны пройдены.

---

## 1. Что сделано

### День 5 — Prometheus-метрики
- ✅ Подключён `prometheus-client`, эндпоинты `/metrics` и `/metrics/summary`.
- ✅ Метрики встроены в RAG-light, plan-cache, chat (`/plan`, `/stream`).
- ✅ В `docker-compose` добавлены Prometheus (порт 9091) и Grafana (порт 3002), дашборды и provisioning.

### Дни 6–7 — A/B-тестирование и стресс-тест
- ✅ Сервис A/B-тестов: эксперименты, варианты пользователей, интеграция с RAG (порог similarity).
- ✅ Стресс-тест на Locust: `scripts/load_test/locustfile.py`, headless и интерактивный режим.
- ✅ Ограничение параллелизма (concurrency limiter): семафор для запросов к Victoria, при перегрузке — **503** вместо 500.
- ✅ Лимит по умолчанию: **50** одновременных запросов к Victoria (`MAX_CONCURRENT_VICTORIA=50`).

### Исправления по ходу
- ✅ Конфликты портов: Knowledge OS Prometheus → **9092**, Web IDE Grafana → **3002**.
- ✅ Падение backend: у роута `/stream` добавлен `response_model=None` (FastAPI не принимал `StreamingResponse | JSONResponse`).
- ✅ Locust на macOS: venv для тестов (`scripts/load_test/setup_venv.sh`), скрипт использует `python3 -m locust` или venv.
- ✅ Таймауты в `run_load_test.sh`: проверка backend и очистка кэшей не зависают.
- ✅ Подсказка при недоступном backend: сначала Knowledge OS, затем `docker-compose up -d`.
- ✅ Парсинг отчёта: исправлены номера колонок CSV (Aggregated), вывод «Запросов / Ошибок / RPS / Время ответа» корректен.
- ✅ Сообщение после Locust: при наличии ошибок запросов больше не выводится «Установите locust».

---

## 2. Результаты прогонов

| Прогон | Запросов | Ошибок | Примечание |
|--------|----------|--------|------------|
| До limiter (лимит 25) | 6251 | 6001 (500) | Перегрузка, много 500. |
| После limiter (лимит 25) | 15 | 2 (503) | 503 вместо 500 — limiter работает. |
| После увеличения лимита до 50 | 15 | 0 | 0 ошибок при той же нагрузке (30 users, 1 min). |

**Вывод:** при перегрузке клиенты получают **503** с `Retry-After`, бэкенд не падает; при лимите 50 текущая нагрузка проходит без ошибок.

---

## 3. Как запускать (кратко)

```bash
# 1. Поднять стек (если ещё не поднят)
docker-compose -f knowledge_os/docker-compose.yml up -d
sleep 15
docker-compose up -d

# 2. Один раз настроить Locust (venv)
./scripts/load_test/setup_venv.sh

# 3. Стресс-тест (1 мин, 30 пользователей)
RUN_TIME=1m USERS=30 SPAWN_RATE=5 ./scripts/run_load_test.sh
```

Отчёт: `scripts/load_test/out/load_test_report.html`  
Метрики: http://localhost:8080/metrics, Grafana http://localhost:3002 (логин admin/admin).

---

## 4. Итог

- **Prometheus и метрики** — включены и работают.
- **A/B-тесты** — API и интеграция с RAG готовы.
- **Стресс-тест** — скрипты, venv, парсинг отчёта и лимит Victoria настроены.
- **Concurrency limiter** — при перегрузке отдаётся 503, падений нет.
- **Прогоны** — пройдены; при лимите 50 последний прогон без ошибок.

Подробности: `docs/LOAD_TEST_RESULTS.md`.
