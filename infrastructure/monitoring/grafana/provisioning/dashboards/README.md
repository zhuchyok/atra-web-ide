# Grafana provisioning dashboards

Все JSON-дашборды в этой папке подхватываются Grafana автоматически.

- **dashboard.yml** — провайдер (path: эта же папка).
- **atra-dashboard.json** — копия из `knowledge_os/dashboard/grafana_dashboard.json`.  
  При изменении исходника скопируйте:  
  `cp knowledge_os/dashboard/grafana_dashboard.json infrastructure/monitoring/grafana/provisioning/dashboards/atra-dashboard.json`
- **enhanced-dashboard.json** — копия из `infrastructure/monitoring/grafana/enhanced_dashboard.json`.

Один общий каталог используется в `knowledge_os/docker-compose.yml` (без монтирования отдельных файлов), чтобы избежать ошибки read-only file system.
