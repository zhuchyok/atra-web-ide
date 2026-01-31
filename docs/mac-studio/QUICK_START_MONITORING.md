# 🚀 Быстрый старт: Мониторинг и логирование

**Дата:** 2026-01-25  
**Статус:** ✅ Все сервисы запущены и работают

---

## ✅ ТЕКУЩИЙ СТАТУС

### Запущенные сервисы:

- ✅ **Prometheus** — http://localhost:9090
- ✅ **Grafana** — http://localhost:3001 (admin/atra2025)
- ✅ **Elasticsearch** — http://localhost:9200
- ✅ **Kibana** — http://localhost:5601

---

## 📊 GRAFANA: Настройка за 2 минуты

### 1. Откройте Grafana:
```
http://localhost:3001
Логин: admin
Пароль: atra2025
```

### 2. Добавьте Prometheus datasource:
1. Settings → Data Sources → Add data source
2. Выберите **Prometheus**
3. URL: `http://atra-prometheus:9090`
4. Нажмите **Save & Test**

### 3. Импортируйте дашборд:
1. Dashboards → Import
2. Загрузите файл: `knowledge_os/dashboard/grafana_dashboard.json`
3. Выберите Prometheus datasource
4. Нажмите **Import**

**Готово!** Теперь вы видите метрики производительности.

---

## 🔍 KIBANA: Настройка за 2 минуты

### 1. Откройте Kibana:
```
http://localhost:5601
```

### 2. Создайте index pattern:
1. Management → Stack Management → Index Patterns
2. Нажмите **Create index pattern**
3. Pattern: `atra-logs-*`
4. Time field: `@timestamp`
5. Нажмите **Create index pattern**

### 3. Просмотр логов:
1. Analytics → Discover
2. Выберите index pattern `atra-logs-*`
3. Просматривайте логи в реальном времени

**Готово!** Теперь вы можете искать по всем логам.

---

## 🔧 ВКЛЮЧЕНИЕ ELK ЛОГИРОВАНИЯ

### Для включения ELK логирования:

1. **Добавьте переменные окружения** в `docker-compose.yml`:

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

2. **Перезапустите контейнеры:**

```bash
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent veronica-agent
```

3. **Проверьте логи в Kibana:**

Откройте Kibana → Discover → выберите `atra-logs-*`

---

## 📋 КОМАНДЫ УПРАВЛЕНИЯ

### Запуск всех сервисов мониторинга:
```bash
docker-compose -f knowledge_os/docker-compose.yml up -d prometheus grafana elasticsearch kibana
```

### Остановка:
```bash
docker-compose -f knowledge_os/docker-compose.yml stop prometheus grafana elasticsearch kibana
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

## 🎯 ЧТО МОЖНО ДЕЛАТЬ

### В Grafana:
- 📊 Смотреть метрики производительности
- 📈 Анализировать тренды
- 🚨 Настраивать алерты
- 📉 Отслеживать использование ресурсов

### В Kibana:
- 🔍 Искать по всем логам
- 📊 Визуализировать паттерны в логах
- 🚨 Настраивать алерты на основе логов
- 📈 Анализировать ошибки и производительность

---

## ✅ ВСЕ ГОТОВО!

Все сервисы мониторинга и логирования запущены и работают.

**Следующий шаг:** Настройте Grafana и Kibana по инструкциям выше.

---

*Создано 2026-01-25*
