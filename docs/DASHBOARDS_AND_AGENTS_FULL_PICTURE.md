# Полная картина: дашборды и агенты ATRA Web IDE

Единый справочник всех дашбордов, UI агентов и точек входа для мониторинга и управления. Для верификации и использования в будущем.

**Связанные документы:** [PROJECT_ARCHITECTURE_AND_GUIDE.md](PROJECT_ARCHITECTURE_AND_GUIDE.md), [GRAFANA_SETUP.md](GRAFANA_SETUP.md), план верификации (агенты, оркестраторы, эксперты).

---

## 1. Сводная таблица: дашборды и порты

| Компонент | Порт (хост) | URL | Логин / пароль | Назначение |
|-----------|-------------|-----|----------------|------------|
| **Grafana (Web IDE)** | 3002 | http://localhost:3002 | admin / admin | Метрики чата, бэкенда, RAG, планов (Prometheus 9091). |
| **Grafana (Knowledge OS)** | 3001 | http://localhost:3001 | admin / atra2025 | Оркестрация, БЗ, агенты, A/B, обзор (Prometheus 9092). |
| **Corporation Dashboard (Streamlit)** | 8501 | http://localhost:8501 | — | Задачи, эксперты, разведка, симуляции, маркетинг, A/B; источник задач: dashboard_simulator, dashboard_scout, dashboard_marketing, dashboard_submit. |
| **Quality dashboard (HTML)** | — | quality_dashboard.html (файл) | — | Генерируется скриптом create_simple_dashboard.py; история качества, алерты. |
| **Frontend (чат Web IDE)** | 3000 → 3002 | http://localhost:3002 | — | Чат с Victoria; Backend 8080 → Victoria 8010. |

**Примечание:** Frontend в docker-compose Web IDE проброшен на 3002 (3000 занят); Grafana Knowledge OS — на 3001.

---

## 2. Grafana (Web IDE) — порт 3002

- **Где:** `docker-compose.yml` (корень), сервис `grafana`; образ `grafana/grafana:latest`; контейнер `atra-web-ide-grafana`.
- **Provisioning:** `grafana/provisioning/` (datasources, dashboards); дашборды: `grafana/dashboards/chat-metrics.json`.
- **Левая панель:** дашборды сгруппированы в папку **«Web IDE»** (folder в `grafana/provisioning/dashboards/dashboard.yml`) — в боковом меню Dashboards → папка «Web IDE» → Chat System Metrics.
- **Источник данных:** Prometheus Web IDE — порт 9091 (внутри сети: `http://prometheus:9090`).
- **Панели (Chat System Metrics):**
  - Requests per second: `rate(chat_requests_total[5m])`
  - Request Duration (p95): histogram по chat_request_duration_seconds
  - RAG Cache Hit Rate, Active Requests, Plan Requests Total, Errors
- **Метрики бэкенда:** http://localhost:8080/metrics, http://localhost:8080/metrics/summary
- **Документация:** [GRAFANA_SETUP.md](GRAFANA_SETUP.md)

---

## 3. Grafana (Knowledge OS) — порт 3001

- **Где:** `knowledge_os/docker-compose.yml`, сервис `grafana`, контейнер `atra-grafana`; порт `3001:3000`.
- **Provisioning:** `infrastructure/monitoring/grafana/provisioning/` (datasources: prometheus.yml; dashboards: папка с JSON).
- **Левая панель:** дашборды сгруппированы в папку **«Knowledge OS»** (folder в `infrastructure/monitoring/grafana/provisioning/dashboards/dashboard.yml`) — в боковом меню Dashboards → папка «Knowledge OS» → atra, enhanced, orchestration, overview.
- **Источник данных:** Prometheus Knowledge OS — порт 9092 (внутри сети: `http://prometheus:9090`).
- **Дашборды (автоподхват из папки):**
  - **dashboard.yml** — провайдер (path: та же папка).
  - **atra-dashboard.json** — копия из `knowledge_os/dashboard/grafana_dashboard.json`.
  - **enhanced-dashboard.json** — копия из `infrastructure/monitoring/grafana/enhanced_dashboard.json`.
  - **orchestration.json**, **orchestration_ab.json** — оркестрация и A/B-тест.
  - **overview.json** — обзор.
- **Обновление atra-dashboard:**  
  `cp knowledge_os/dashboard/grafana_dashboard.json infrastructure/monitoring/grafana/provisioning/dashboards/atra-dashboard.json`
- **Документация:** [GRAFANA_SETUP.md](GRAFANA_SETUP.md)

---

## 4. Corporation Dashboard (Streamlit) — порт 8501

- **Где:** `knowledge_os/dashboard/app.py`; контейнер `corporation-dashboard` в `knowledge_os/docker-compose.yml`; порт `8501:8501`.
- **Навигация (2026-02-04):** в сайдбаре — **6 разделов** (мировые практики: 5–7 пунктов, прогрессивное раскрытие): **Обзор**, **Задачи**, **Разведка и симуляции**, **Стратегия и эксперты**, **Аналитика и качество**, **Система и агент**. При выборе раздела рендерятся **только подвкладки этого раздела** (ленивая загрузка). Обзор — единая точка входа (st.stop); Задачи — 2 подвкладки; Разведка и симуляции — 3; Стратегия и эксперты — 5 (Ликвидность, Структура, OKR, Решения Совета, Академия ИИ); Аналитика и качество / Система и агент — заглушки (подвкладки по плану). Блок из 23 вкладок удалён. См. CHANGES_FROM_OTHER_CHATS §0.3j, DASHBOARD_OPTIMIZATION_PLAN.
- **Запуск:** `streamlit run app.py --server.port=8501 --server.address=0.0.0.0`; рабочая директория в Docker: `/app/project/knowledge_os/dashboard`.
- **БД:** `DATABASE_URL` (knowledge_postgres в Docker); дашборд читает/пишет задачи, экспертов, узлы знаний.
- **Источники задач (metadata.source):**
  - **dashboard_simulator** — симуляции бизнес-идей (задачи создаются из дашборда).
  - **dashboard_scout** — разведка (бизнес-разведка, анализ рынков).
  - **dashboard_marketing** — маркетинговые задачи.
  - **dashboard_submit** — ручная отправка с дашборда.
  - **nightly**, **chat**, **api** — другие источники (для фильтрации в UI).
- **Обработка задач:** созданные задачи попадают в таблицу `tasks` с `assignee_expert_id = NULL` или назначенным; Enhanced Orchestrator и Smart Worker обрабатывают их (см. [ARCHITECTURE_FULL.md](ARCHITECTURE_FULL.md)).
- **Специальные обработчики в Smart Worker:**  
  `source == 'scout_orchestrator' | 'dashboard_scout' | 'enhanced_scout_orchestrator'` → `scout_task_processor`;  
  `source == 'dashboard_simulator'` → симулятор.
- **Связь с агентами:** дашборд не вызывает Victoria/Veronica напрямую; создаёт задачи в БД, оркестратор и воркер выполняют через экспертов и ai_core.
- **Память:** известна высокая потребность в RAM (~11.5 ГБ); см. [DASHBOARD_OPTIMIZATION_PLAN.md](DASHBOARD_OPTIMIZATION_PLAN.md).

---

## 5. Quality dashboard (HTML)

- **Где:** генерируется скриптом `scripts/create_simple_dashboard.py`; выходной файл: `quality_dashboard.html` (в корне репо или указанный путь).
- **Назначение:** история качества, последние результаты, алерты; статический HTML, без отдельного порта.
- **Использование:** открыть файл в браузере после запуска скрипта.

---

## 6. Агенты: точки входа и UI

| Агент / сервис | Порт | Точка входа (UI/API) | Как проверить |
|----------------|------|----------------------|----------------|
| **Victoria** | 8010 | Backend → POST :8010/run; чат Web IDE (Frontend 3002 → Backend 8080 → Victoria); Telegram-бот | GET http://localhost:8010/status → victoria_levels: agent, enhanced, initiative |
| **Veronica** | 8011 | Вызывается только Victoria (POST :8011/run) | GET http://localhost:8011/status или health |
| **Backend (чат/план)** | 8080 | POST /api/chat/stream, POST /api/chat/plan; Frontend 3002 | GET http://localhost:8080/health |
| **Frontend (чат)** | 3002 | Браузер: http://localhost:3002 — чат с Victoria | Открыть в браузере |
| **REST API Knowledge OS** | 8012 | Метрики, здоровье, задачи (если запущен) | GET :8012/health, GET :8012/metrics |

Чат всегда идёт: Пользователь → Frontend (3002) или API → Backend (8080) → Victoria (8010). Оркестратор и задачи в БД — отдельный поток (Enhanced Orchestrator, Smart Worker).

---

## 7. Связь дашбордов с агентами и оркестраторами

- **Grafana Web IDE (3002):** метрики запросов к чату и бэкенду (которые идут в Victoria).
- **Grafana Knowledge OS (3001):** метрики оркестрации, A/B, воркера, БЗ — то есть того, что обслуживает задачи из БД и агентов.
- **Corporation Dashboard (8501):** создаёт задачи в БД; оркестратор назначает экспертов; Smart Worker выполняет через ai_core (эксперты + Ollama/MLX). Дашборд показывает задачи, экспертов, разведку, симуляции — это «пульт управления» корпорацией, а не прямой вызов Victoria/Veronica.

Итог: для полной картины нужны оба Grafana (3002 — чат/бэкенд, 3001 — оркестрация/агенты/БЗ) и Corporation Dashboard (8501) для создания и просмотра задач и экспертов.

---

## 8. Что проверять при верификации

- [ ] Grafana Web IDE: http://localhost:3002 открывается, Data source Prometheus (9091) в статусе Working, дашборд Chat System Metrics показывает данные после запросов в чат.
- [ ] Grafana Knowledge OS: http://localhost:3001 открывается (admin/atra2025), дашборды (atra, enhanced, orchestration, overview) подхвачены и отображают данные.
- [ ] Corporation Dashboard: http://localhost:8501 открывается, список задач/экспертов загружается, создание задачи (например, разведка или симуляция) создаёт запись в БД и в итоге обрабатывается воркером.
- [ ] Чат: http://localhost:3002 → чат с Victoria; ответы приходят без эхо; при перегрузке бэкенд возвращает 503 с Retry-After.
- [ ] Victoria/Veronica: GET :8010/status и :8011/status возвращают ожидаемые поля (victoria_levels и т.д.).

---

*Документ актуализирован для использования в плане верификации и при настройке/проверке дашбордов и агентов.*
