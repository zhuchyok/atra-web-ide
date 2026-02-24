# 📊 Полное руководство по настройке мониторинга и логирования

**Дата:** 2026-01-25  
**Статус:** ✅ Все компоненты реализованы и готовы к настройке

---

## 🎯 ЧТО РЕАЛИЗОВАНО

### ✅ Prometheus + Grafana

- Контейнеры запущены и работают
- Автоматическая настройка datasource через provisioning
- Дашборд готов к импорту

### ✅ ELK стек (Elasticsearch + Kibana)

- Контейнеры запущены и работают
- ELKHandler создан и готов к использованию
- Интеграция в систему логирования

---

## 🚀 ПОШАГОВАЯ НАСТРОЙКА

### Шаг 1: Проверка статуса сервисов

```bash
# Проверка всех сервисов
docker ps | grep -E "(prometheus|grafana|elastic|kibana)"

# Должны быть запущены:
# - atra-prometheus (порт 9090)
# - atra-grafana (порт 3001)
# - atra-elasticsearch (порт 9200)
# - atra-kibana (порт 5601)
```

**Ожидаемый результат:** Все 4 контейнера в статусе "Up"

---

### Шаг 2: Настройка Grafana (автоматически)

```bash
# Автоматическая настройка Grafana
bash scripts/setup_grafana_complete.sh
```

**Что делает скрипт:**

1. ✅ Проверяет доступность Grafana
2. ✅ Создает Prometheus datasource (если не существует)
3. ✅ Импортирует дашборд
4. ✅ Выводит ссылку на дашборд

**Или вручную:**

1. Откройте http://localhost:3001
2. Логин: `admin`, пароль: `atra2025`
3. Settings → Data Sources → Add data source
4. Выберите Prometheus
5. URL: `http://atra-prometheus:9090`
6. Save & Test
7. Dashboards → Import → загрузите `knowledge_os/dashboard/grafana_dashboard.json`

---

### Шаг 3: Настройка Kibana

```bash
# Показать инструкции
bash scripts/setup_kibana_complete.sh
```

**Или вручную:**

1. Откройте http://localhost:5601
2. Management → Stack Management → Index Patterns
3. Create index pattern
4. Pattern: `atra-logs-*`
5. Time field: `@timestamp`
6. Create index pattern

**Примечание:** Index pattern можно создать только после появления первых логов.

---

### Шаг 4: Включение ELK логирования

#### Вариант 1: Через docker-compose.yml (рекомендуется)

Добавьте в `knowledge_os/docker-compose.yml` для нужных контейнеров:

```yaml
victoria-agent:
  environment:
    # ... существующие переменные ...
    - USE_ELK=true
    - ELASTICSEARCH_URL=http://atra-elasticsearch:9200

veronica-agent:
  environment:
    # ... существующие переменные ...
    - USE_ELK=true
    - ELASTICSEARCH_URL=http://atra-elasticsearch:9200
```

Затем перезапустите:

```bash
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent veronica-agent
```

#### Вариант 2: Через переменные окружения при запуске

```bash
docker exec -e USE_ELK=true -e ELASTICSEARCH_URL=http://atra-elasticsearch:9200 knowledge_os_api python main.py
```

---

### Шаг 5: Проверка работы

#### Prometheus:

```bash
# Проверка targets
curl http://localhost:9090/api/v1/targets | python3 -m json.tool

# Проверка метрик
curl http://localhost:9090/api/v1/query?query=up
```

#### Grafana:

```bash
# Проверка datasources
curl -u admin:atra2025 http://localhost:3001/api/datasources | python3 -m json.tool
```

#### Elasticsearch:

```bash
# Проверка индексов
curl 'http://localhost:9200/_cat/indices?v'

# Проверка здоровья
curl http://localhost:9200/_cluster/health
```

#### Kibana:

```bash
# Проверка статуса
curl http://localhost:5601/api/status | python3 -m json.tool
```

---

## 🔧 РЕШЕНИЕ ПРОБЛЕМ

### Проблема: Prometheus не может получить метрики

**Симптом:** Target показывает "down" с ошибкой 404

**Решение:**

1. Проверьте, что `/metrics` endpoint доступен:
   ```bash
   curl http://localhost:8000/metrics
   ```
2. Если 404, перезапустите контейнер `knowledge_os_api`:
   ```bash
   docker restart knowledge_os_api
   ```
3. Проверьте логи контейнера:
   ```bash
   docker logs knowledge_os_api | tail -20
   ```

---

### Проблема: Grafana не видит Prometheus

**Симптом:** Datasource показывает ошибку подключения

**Решение:**

1. Проверьте, что Prometheus доступен из контейнера Grafana:
   ```bash
   docker exec atra-grafana curl http://atra-prometheus:9090/-/healthy
   ```
2. Проверьте сеть:
   ```bash
   docker network inspect atra-network | grep -A 5 "prometheus\|grafana"
   ```
3. Пересоздайте datasource через UI

---

### Проблема: Логи не появляются в Kibana

**Симптом:** Index pattern создан, но нет данных

**Решение:**

1. Проверьте, что ELK логирование включено:
   ```bash
   docker exec victoria-agent env | grep USE_ELK
   ```
2. Проверьте логи контейнера:
   ```bash
   docker logs victoria-agent | grep -i elk
   ```
3. Проверьте индексы в Elasticsearch:
   ```bash
   curl 'http://localhost:9200/_cat/indices?v' | grep atra-logs
   ```
4. Если индексов нет, проверьте подключение к Elasticsearch:
   ```bash
   docker exec victoria-agent curl http://atra-elasticsearch:9200/_cluster/health
   ```

---

## 📋 ПРОВЕРОЧНЫЙ ЧЕКЛИСТ

### Базовая инфраструктура:

- [ ] Docker Desktop запущен
- [ ] Все контейнеры запущены (`docker ps`)
- [ ] Сеть `atra-network` существует

### Prometheus:

- [ ] Доступен на http://localhost:9090
- [ ] Targets видны в UI
- [ ] Метрики собираются

### Grafana:

- [ ] Доступен на http://localhost:3001
- [ ] Prometheus datasource настроен
- [ ] Дашборд импортирован
- [ ] Метрики отображаются

### Elasticsearch:

- [ ] Доступен на http://localhost:9200
- [ ] Health status: green
- [ ] Индексы создаются при логировании

### Kibana:

- [ ] Доступен на http://localhost:5601
- [ ] Index pattern `atra-logs-*` создан
- [ ] Логи отображаются в Discover

### ELK логирование:

- [ ] `USE_ELK=true` в переменных окружения
- [ ] Логи отправляются в Elasticsearch
- [ ] Логи видны в Kibana

---

## 🎯 БЫСТРЫЕ КОМАНДЫ

### Запуск всех сервисов:

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d prometheus grafana elasticsearch kibana
```

### Остановка:

```bash
docker-compose -f knowledge_os/docker-compose.yml stop prometheus grafana elasticsearch kibana
```

### Перезапуск:

```bash
docker-compose -f knowledge_os/docker-compose.yml restart prometheus grafana elasticsearch kibana
```

### Просмотр логов:

```bash
docker logs atra-prometheus -f
docker logs atra-grafana -f
docker logs atra-elasticsearch -f
docker logs atra-kibana -f
```

### Проверка статуса:

```bash
docker ps | grep -E "(prometheus|grafana|elastic|kibana)"
```

---

## 📊 ДОСТУП К СЕРВИСАМ

| Сервис            | URL                   | Логин | Пароль   |
| ----------------- | --------------------- | ----- | -------- |
| **Prometheus**    | http://localhost:9090 | -     | -        |
| **Grafana**       | http://localhost:3001 | admin | atra2025 |
| **Elasticsearch** | http://localhost:9200 | -     | -        |
| **Kibana**        | http://localhost:5601 | -     | -        |

---

## ✅ ИТОГ

После выполнения всех шагов:

- ✅ Prometheus собирает метрики
- ✅ Grafana визуализирует метрики
- ✅ Elasticsearch хранит логи
- ✅ Kibana анализирует логи
- ✅ Все компоненты работают вместе

**Корпорация ATRA имеет полный мониторинг и логирование!**

---

_Руководство создано 2026-01-25_
