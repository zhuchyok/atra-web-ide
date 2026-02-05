# Настройка Grafana для метрик ATRA Web IDE (День 5)

В проекте два экземпляра Grafana:
- **Web IDE:** http://localhost:**3002** (логин `admin` / пароль `admin`) — дашборды чата, метрики бэкенда. В левой панели дашборды сгруппированы в папку **«Web IDE»**.
- **Knowledge OS:** http://localhost:**3001** (логин `admin` / пароль `atra2025`) — дашборды оркестрации, БЗ, агентов. В левой панели дашборды сгруппированы в папку **«Knowledge OS»**.

## 1. Вход в Grafana (Web IDE)

- **URL:** http://localhost:3002  
- **Логин:** `admin`  
- **Пароль:** `admin`  

При первом входе Grafana может предложить сменить пароль — можно сменить или нажать «Skip».

---

## 2. Источник данных (Prometheus)

### Если datasource уже подставлен через provisioning

1. Меню слева: **Connections** (или **Configuration**) → **Data sources**.
2. Должен быть источник **Prometheus** с URL `http://prometheus:9090` и статусом **Working** (зелёная галочка).
3. Если статус **Connection failed** — см. раздел «Если Prometheus не подключается» ниже.

### Если источника нет — добавить вручную

1. **Connections** → **Data sources** → **Add data source**.
2. Выбрать **Prometheus**.
3. Заполнить:
   - **Name:** `Prometheus` (или любое имя).
   - **URL:**  
     - из контейнера Grafana (тот же docker-compose): `http://prometheus:9090`  
     - если Grafana на хосте, а Prometheus в Docker: `http://localhost:9091`
4. **Save & test**. Должно быть **Data source is working**.

---

## 3. Дашборд «Chat System Metrics»

### Вариант A: Дашборд подхватился из папки (provisioning)

1. Меню слева: **Dashboards**.
2. В списке найти **Chat System Metrics** и открыть его.
3. Если панели пустые — убедиться, что выбран источник **Prometheus** и что бэкенд уже отдавал метрики (сделать пару запросов в чат/план).

### Вариант B: Импорт дашборда вручную

1. **Dashboards** → **New** → **Import** (или **Import dashboard**).
2. **Import via panel.json** — нажать **Upload JSON file**.
3. Указать файл:  
   `atra-web-ide/grafana/dashboards/chat-metrics.json`
4. Внизу выбрать **Prometheus** в поле **Prometheus**.
5. **Import**.

### Вариант C: Импорт по ID (если позже выложите в grafana.com)

1. **Dashboards** → **Import**.
2. Ввести **Import via grafana.com** ID (когда будет).
3. Выбрать **Prometheus** → **Import**.

---

## 4. Что есть на дашборде

| Панель | Метрика | Описание |
|--------|---------|----------|
| **Requests per second** | `rate(chat_requests_total[5m])` | RPS по режимам/эндпоинтам (plan, stream и т.д.) |
| **Request Duration (p95)** | `histogram_quantile(0.95, ...)` | 95-й перцентиль времени ответа |
| **RAG Cache Hit Rate** | `rate(rag_cache_hits_total[5m]) / rate(rag_requests_total[5m])` | Доля попаданий в кэш RAG |
| **Active Requests** | `active_requests` | Текущее число активных запросов |
| **Plan Requests Total** | `increase(plan_requests_total[1h])` | Число запросов планов за последний час |
| **Errors** | `rate(errors_total[5m])` | Частота ошибок по типу и компоненту |

Данные появятся после того, как бэкенд обработает запросы (чат, план, RAG). Можно обновить дашборд кнопкой **Refresh** или выставить авто-обновление (например, каждые 10s).

---

## 5. Если Prometheus не подключается

- **Grafana и Prometheus в одном docker-compose (atra-web-ide):**  
  URL должен быть `http://prometheus:9090` (имя сервиса и внутренний порт).

- **Prometheus на хосте (например, только порт 9091):**  
  В Data source указать `http://host.docker.internal:9091` (если Grafana в Docker) или `http://localhost:9091` (если Grafana на хосте).

- **Проверка с хоста:**  
  `curl -s http://localhost:9091/api/v1/targets` — в ответе должны быть targets (наш — `chat-backend`).

- **Перезапуск Grafana после смены URL:**  
  `docker compose restart grafana`.

---

## 6. Полезные ссылки

- Grafana Web IDE: http://localhost:3002  
- Grafana Knowledge OS: http://localhost:3001  
- Prometheus Web IDE (порт 9091): http://localhost:9091  
- Метрики бэкенда (сырой вывод): http://localhost:8080/metrics  
- Сводка метрик: http://localhost:8080/metrics/summary  

---

## 7. Смена пароля admin (рекомендуется)

1. Слева: иконка пользователя → **Profile** → **Change password**.
2. Задать новый пароль и сохранить.
