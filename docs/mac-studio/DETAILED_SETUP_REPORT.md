# 📊 Детальный отчет по настройке мониторинга

**Дата:** 2026-01-25  
**Статус:** ✅ Реализация завершена, настройка в процессе

---

## 🔍 ТЕКУЩИЙ СТАТУС

### ✅ Запущенные сервисы:

```
atra-prometheus         Up (порт 9090) — работает ✅
atra-grafana            Up (порт 3001) — работает ✅
atra-elasticsearch      Up (порт 9200) — работает, healthy ✅
atra-kibana             Up (порт 5601) — работает ✅
```

### ⚠️ Требует настройки:

1. **Grafana datasource** — нужно создать Prometheus datasource
2. **Grafana dashboard** — нужно импортировать дашборд
3. **Kibana index pattern** — нужно создать `atra-logs-*`
4. **ELK логирование** — нужно включить `USE_ELK=true`

---

## 📋 ДЕТАЛЬНАЯ НАСТРОЙКА

### 1. Grafana: Prometheus Datasource

#### Автоматически (через скрипт):

```bash
bash scripts/setup_grafana_complete.sh
```

#### Вручную:

1. Откройте http://localhost:3001
2. Логин: `admin`, пароль: `atra2025`
3. Settings → Data Sources → Add data source
4. Выберите **Prometheus**
5. URL: `http://atra-prometheus:9090`
6. Нажмите **Save & Test**
7. Должно появиться "Data source is working"

---

### 2. Grafana: Импорт дашборда

#### Автоматически (через скрипт):

```bash
bash scripts/setup_grafana_complete.sh
```

#### Вручную:

1. В Grafana: Dashboards → Import
2. Загрузите файл: `knowledge_os/dashboard/grafana_dashboard.json`
3. Выберите Prometheus datasource
4. Нажмите **Import**

---

### 3. Kibana: Index Pattern

#### Вручную (требуется после появления логов):

1. Откройте http://localhost:5601
2. Management → Stack Management → Index Patterns
3. Create index pattern
4. Pattern: `atra-logs-*`
5. Time field: `@timestamp`
6. Create index pattern

**Примечание:** Index pattern можно создать только после появления первых логов в Elasticsearch.

---

### 4. ELK логирование: Включение

#### Добавьте в `docker-compose.yml`:

```yaml
victoria-agent:
  environment:
    - USE_ELK=true
    - ELASTICSEARCH_URL=http://atra-elasticsearch:9200

veronica-agent:
  environment:
    - USE_ELK=true
    - ELASTICSEARCH_URL=http://atra-elasticsearch:9200
```

#### Перезапустите контейнеры:

```bash
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent veronica-agent
```

#### Проверьте логи:

```bash
docker logs victoria-agent | grep -i elk
docker logs veronica-agent | grep -i elk
```

---

## 🔧 ПРОБЛЕМЫ И РЕШЕНИЯ

### Проблема 1: Prometheus targets показывают "down"

**Причина:**

- `/metrics` endpoint возвращает 404
- Контейнеры в разных сетях
- Targets недоступны

**Решение:**

1. Проверьте сеть:
   ```bash
   docker network inspect atra-network | grep -E "(prometheus|victoria|veronica|knowledge_os_api)"
   ```
2. Проверьте `/metrics` endpoint:
   ```bash
   curl http://localhost:8000/metrics
   ```
3. Если 404, перезапустите контейнер:
   ```bash
   docker restart knowledge_os_api
   ```

---

### Проблема 2: Grafana provisioning не работает

**Причина:** Файлы не монтируются правильно

**Решение:**

1. Проверьте монтирование:
   ```bash
   docker exec atra-grafana ls -la /etc/grafana/provisioning/datasources/
   ```
2. Если файлов нет, используйте скрипт настройки:
   ```bash
   bash scripts/setup_grafana_complete.sh
   ```

---

### Проблема 3: Логи не появляются в Elasticsearch

**Причина:** ELK логирование не включено

**Решение:**

1. Проверьте переменные окружения:
   ```bash
   docker exec victoria-agent env | grep USE_ELK
   ```
2. Если пусто, добавьте в `docker-compose.yml` и перезапустите
3. Проверьте логи контейнера:
   ```bash
   docker logs victoria-agent | tail -20
   ```

---

## ✅ ПРОВЕРОЧНЫЙ ЧЕКЛИСТ

### Инфраструктура:

- [x] Docker Desktop запущен
- [x] Все контейнеры запущены
- [x] Сеть `atra-network` существует

### Prometheus:

- [x] Контейнер запущен
- [x] Доступен на http://localhost:9090
- [ ] Targets показывают "up" (требует исправления /metrics endpoint)

### Grafana:

- [x] Контейнер запущен
- [x] Доступен на http://localhost:3001
- [ ] Prometheus datasource создан (требует настройки)
- [ ] Дашборд импортирован (требует настройки)

### Elasticsearch:

- [x] Контейнер запущен и healthy
- [x] Доступен на http://localhost:9200
- [ ] Индексы создаются (требует включения ELK логирования)

### Kibana:

- [x] Контейнер запущен
- [x] Доступен на http://localhost:5601
- [ ] Index pattern создан (требует настройки после появления логов)

---

## 📝 СЛЕДУЮЩИЕ ШАГИ

1. **Настроить Grafana:**

   ```bash
   bash scripts/setup_grafana_complete.sh
   ```

2. **Включить ELK логирование:**
   - Добавить `USE_ELK=true` в docker-compose.yml
   - Перезапустить контейнеры

3. **Настроить Kibana:**
   - Создать index pattern после появления логов

4. **Проверить работу:**
   - Метрики в Grafana
   - Логи в Kibana

---

_Отчет создан 2026-01-25_
