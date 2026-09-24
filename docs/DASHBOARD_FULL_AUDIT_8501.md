# Полный аудит дашборда ATRA Corporation (http://localhost:8501)

**Дата:** 2025-02-23  
**Запуск:** `./scripts/run_dashboard_local.sh` → `knowledge_os/dashboard/app.py` на порту 8501.

## Разделы и вкладки

| Раздел                     | Файл                 | Статус       | Зависимости                                    |
| -------------------------- | -------------------- | ------------ | ---------------------------------------------- |
| **Обзор (Pulse)**          | app.py               | ✅ Работает  | БД, VectorCore (get_embedding), check_services |
| **Wisdom & Mentorship**    | tabs/wisdom_tab.py   | ✅ Исправлен | БД, digital_constitution (fallback path)       |
| **Задачи и SLA**           | tabs/tasks_tab.py    | ✅ Исправлен | БД, run_query, file_comments (опц.)            |
| **Стратегия и ROI**        | tabs/strategy_tab.py | ✅ Исправлен | БД, REST API экспертов (KNOWLEDGE_REST_URL)    |
| **Интеллект (RAG)**        | tabs/data_tab.py     | ✅ Исправлен | БД, run_query, knowledge_links, graph_utils    |
| **Инструменты экспертов**  | tabs/scout_tab.py    | ✅ Исправлен | БД, db_connection(), simulations               |
| **Система и Безопасность** | tabs/system_tab.py   | ✅ Исправлен | БД, check_services, BACKEND_URL, Docker (опц.) |

## Что проверено и исправлено

### 1. Подключение к БД и пул

- **Проблема:** `get_db_connection()` возвращал соединение из пула; при использовании в `with get_db_connection() as conn` соединение не возвращалось в пул → утечка.
- **Исправление:** В `database_service.py` добавлен контекстный менеджер `db_connection()`, который в `finally` вызывает `putconn(conn)`. Во всех местах в `scout_tab.py` заменён вызов на `with db_connection() as conn` и добавлена проверка `if not conn`.

### 2. Вкладка «Задачи»

- **Проблема:** Опечатка `submitted = st.form_submit_state = st.form_submit_button(...)` — кнопка «Создать задачу» не работала.
- **Исправление:** Заменено на `submitted = st.form_submit_button(...)`.

### 3. Вкладка «Интеллект» (data_tab)

- **Проблема:** В `render_prompt_battle` использовался `run_query` без импорта; в `render_revision` кнопка «Подтвердить» не вызывала обновление БД.
- **Исправление:** В начало файла добавлен импорт `run_query` из `database_service`. В ревизии при нажатии «Подтвердить» вызывается `run_query("UPDATE knowledge_nodes SET is_verified = true WHERE id = %s", ...)` и выполняется `st.rerun()`.

### 4. Вкладка «Стратегия» (strategy_tab)

- **Проблема:** SQL-инъекция в запросе по эксперту (`id = '{exp_data['id']}'`); API экспертов захардкожен как `http://knowledge_rest:8002` (не работает локально).
- **Исправление:** Запрос переведён на параметризованный `WHERE id = %s`, `(str(exp_data["id"]),)`. URL API вынесен в переменную `REST_API_URL` из `KNOWLEDGE_REST_URL` / `REST_API_URL` (по умолчанию `http://localhost:8002`). Вызовы переведены на `httpx` вместо `requests`.
- **Финансы:** Запрос с `virtual_budget` / `performance_score` обёрнут в try/except на случай отсутствия колонок в схеме.

### 5. Вкладка «Инструменты» (scout_tab)

- Все использования `get_db_connection()` заменены на `db_connection()` с проверкой `if not conn`. Исправлены отступы в блоках маркетинга и разведки после замены.

### 6. Вкладка «Система» (system_tab)

- В начало модуля добавлен `import requests`, чтобы блок «Последние эксперименты» не падал при отсутствии `requests` в области видимости.
- **Безопасность:** При отсутствии таблицы `anomaly_detection_logs` показывается сообщение «Модуль угроз не настроен».
- **War Room:** Загрузка сессий из `expert_discussions` обёрнута в try/except; при ошибке показывается информационное сообщение.

### 7. Wisdom

- Импорт `digital_constitution`: при `ImportError` выполняется добавление `knowledge_os/app` в `sys.path` и повторный импорт.

### 8. Обзор (app.py)

- Блоки «Пульс» (алерты безопасности, решения совета, AI Research) при исключении показывают короткое сообщение вместо тихого `pass`.

## Зависимости от таблиц и сервисов

- **Обязательные:** `tasks`, `experts`, `knowledge_nodes`, `domains`, `projects`.
- **Опциональные:** `anomaly_detection_logs`, `expert_discussions`, `simulations`, `knowledge_links`, `file_comments`, `interaction_logs`, `okrs`, `expert_mutations`, `semantic_ai_cache` (для метрик).
- **Сервисы:** PostgreSQL (обязателен), VectorCore (для поиска в Обзоре), MLX API / Ollama (check_services), при необходимости REST API экспертов и backend для песочницы.

## Рекомендации

1. **Локальный запуск:** Задать `KNOWLEDGE_REST_URL=http://localhost:8002` или использовать Rust Gateway для экспертов, если доступен.
2. **Таблица `simulations`:** Для вкладки «Симулятор» должна существовать (миграция при необходимости).
3. **Песочница и эксперименты:** Требуют доступный backend (`BACKEND_URL`, по умолчанию `http://localhost:8080`); при недоступности показываются ошибки связи.

Аудит выполнен пошагово по каждой вкладке и ключевым функциям; все выявленные проблемы исправлены в коде.

---

## Проверка запуска (2026-02-24)

- Дашборд запускается через `knowledge_os/.venv` (или системный python3):  
  `./scripts/run_dashboard_local.sh` или из папки дашборда:  
  `../.venv/bin/python -m streamlit run app.py --server.port=8501 --server.address=127.0.0.1`
- HTTP: `GET http://127.0.0.1:8501/` возвращает **200**.
- Слой данных проверяется скриптом **knowledge_os/dashboard/verify_dashboard_data.py** (без браузера):
  - Подключение к БД (`quick_db_check`), `fetch_parallel` (шапка), запросы по разделам Обзор, Wisdom, Задачи, Стратегия, Интеллект, Инструменты (`db_connection`, simulations), Система (`check_services`, expert_discussions).
  - Запуск: `cd knowledge_os/dashboard && ../.venv/bin/python verify_dashboard_data.py`
  - Все проверки пройдены при доступной PostgreSQL.
