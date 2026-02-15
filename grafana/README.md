# Grafana (Web IDE)

- **URL:** http://localhost:3002 (логин `admin` / пароль `admin`)
- **Образ:** `grafana/grafana:10.2.3` (фиксированная версия; latest давал ошибку provisioning).
- **Provisioning:** datasources (Prometheus), dashboards (папка «Web IDE»), alerting (алерт deferred_to_human) подхватываются при старте.

## Порядок при старте

1. **Prometheus** поднимается первым (healthcheck).
2. **Grafana** зависит от `prometheus` (condition: service_healthy) и при старте подхватывает:
   - **Datasource** Prometheus, URL `http://atra-prometheus:9090`, uid `prometheus`.
   - **Дашборды** из `provisioning/dashboards/` (папка «Web IDE»).
   - **Алерты** из `provisioning/alerting/` (в т.ч. deferred_to_human, ссылается на datasource uid `prometheus`).

Запуск: из корня проекта `docker compose up -d` (сначала поднимется Prometheus, затем Grafana). Если Grafana уже была остановлена: `docker compose up -d grafana`.
