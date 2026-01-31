# 📊 План реализации ELK стека и Grafana

**Дата:** 2026-01-25  
**Статус:** Анализ завершен, план готов к реализации

---

## 🔍 АНАЛИЗ: ДЛЯ ЧЕГО СОЗДАВАЛИСЬ

### 1. **ELK стек (Elasticsearch + Kibana)**

#### Назначение:
- ✅ **Централизованное логирование** — все логи в одном месте
- ✅ **Поиск по логам** — быстрый поиск по всем логам системы
- ✅ **Анализ логов** — визуализация паттернов, ошибок, производительности
- ✅ **Структурированные логи** — JSON формат с метаданными
- ✅ **Real-time мониторинг** — отслеживание логов в реальном времени

#### Проблемы текущего подхода:
- ❌ Логи разбросаны по файлам (`logs/*.log`)
- ❌ Нет централизованного поиска
- ❌ Сложно анализировать логи от разных компонентов
- ❌ Нет визуализации паттернов в логах
- ❌ Нет алертов на основе логов

#### Что уже есть:
- ✅ Structured logging (structlog) — JSON формат готов
- ✅ Файловое логирование работает
- ❌ Нет интеграции с Elasticsearch

---

### 2. **Grafana**

#### Назначение:
- ✅ **Визуализация метрик** — графики производительности
- ✅ **Дашборды** — единая точка мониторинга
- ✅ **Алерты** — уведомления о проблемах
- ✅ **Исторические данные** — анализ трендов

#### Проблемы текущего подхода:
- ❌ Метрики экспортируются, но не визуализируются
- ❌ Нет дашбордов для мониторинга
- ❌ Нет алертов на основе метрик
- ❌ Сложно отслеживать производительность

#### Что уже есть:
- ✅ `metrics_exporter.py` — экспорт метрик в Prometheus формате
- ✅ `grafana_dashboard.json` — готовый дашборд
- ✅ `setup_grafana.sh` — скрипт настройки
- ✅ `prometheus.yml` — конфигурация Prometheus
- ✅ Prometheus метрики собираются
- ❌ Нет запущенного Grafana
- ❌ Нет запущенного Prometheus
- ❌ Нет подключения к Prometheus

---

## 🎯 ВЫВОД: ЭТО НУЖНО ДОДЕЛАТЬ!

### Почему это важно:

1. **Для корпорации ATRA:**
   - Много компонентов (Victoria, Veronica, Worker, Orchestrator, Nightly Learner)
   - Нужен централизованный мониторинг
   - Нужен анализ производительности
   - Нужны алерты при проблемах

2. **Для масштабирования:**
   - При росте системы файловое логирование станет проблемой
   - Нужна визуализация метрик для оптимизации
   - Нужен анализ паттернов в логах

3. **Для отладки:**
   - Централизованный поиск по логам ускорит отладку
   - Визуализация метрик покажет узкие места
   - Алерты предупредят о проблемах

---

## 📋 ПЛАН РЕАЛИЗАЦИИ

### Этап 1: Grafana + Prometheus (приоритет: ВЫСОКИЙ)

**Почему сначала Grafana:**
- Метрики уже экспортируются
- Дашборд уже готов
- Конфигурация Prometheus уже есть
- Быстро даст визуализацию

**Время:** 2-3 часа  
**Сложность:** Средняя

---

### Этап 2: ELK стек (приоритет: СРЕДНИЙ)

**Почему потом ELK:**
- Требует больше настройки
- Нужна интеграция в код
- Но критично для масштабирования

**Время:** 4-6 часов  
**Сложность:** Высокая

---

## 🚀 КОНКРЕТНЫЙ ПЛАН: GRAFANA + PROMETHEUS

### Шаг 1: Обновить docker-compose.yml

Добавить в `knowledge_os/docker-compose.yml`:

```yaml
services:
  # ... существующие сервисы ...

  prometheus:
    image: prom/prometheus:latest
    container_name: atra-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ../infrastructure/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - atra-network
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: atra-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=atra2025
      - GF_INSTALL_PLUGINS=
      - GF_SERVER_ROOT_URL=http://localhost:3000
    volumes:
      - grafana_data:/var/lib/grafana
      - ../knowledge_os/dashboard/grafana_dashboard.json:/etc/grafana/provisioning/dashboards/dashboard.json
    networks:
      - atra-network
    depends_on:
      - prometheus
    restart: unless-stopped

volumes:
  # ... существующие volumes ...
  prometheus_data:
  grafana_data:
```

### Шаг 2: Обновить prometheus.yml

Обновить `infrastructure/monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  scrape_timeout: 10s

scrape_configs:
  # Knowledge OS API (метрики из metrics_exporter)
  - job_name: 'knowledge_os_api'
    static_configs:
      - targets: ['knowledge_os_api:8000']
    metrics_path: '/metrics'  # Если есть endpoint /metrics
    scrape_interval: 30s

  # Victoria Agent
  - job_name: 'victoria-agent'
    static_configs:
      - targets: ['atra-victoria-agent:8010']
    metrics_path: '/health'
    scrape_interval: 30s

  # Veronica Agent
  - job_name: 'veronica-agent'
    static_configs:
      - targets: ['atra-veronica-agent:8011']
    metrics_path: '/health'
    scrape_interval: 30s

  # Prometheus сам себя
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
```

### Шаг 3: Добавить /metrics endpoint в Knowledge OS API

Если еще нет, добавить в `knowledge_os/app/main.py`:

```python
from metrics_exporter import get_metrics_exporter

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    exporter = get_metrics_exporter()
    metrics_text = await exporter.export_prometheus_metrics()
    return Response(content=metrics_text, media_type="text/plain")
```

### Шаг 4: Запустить

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d prometheus grafana
```

### Шаг 5: Настроить Grafana

1. Открыть http://localhost:3000
2. Логин: `admin`, пароль: `atra2025`
3. Добавить Prometheus datasource:
   - Settings → Data Sources → Add data source
   - Выбрать Prometheus
   - URL: `http://prometheus:9090`
   - Save & Test
4. Импортировать дашборд:
   - Dashboards → Import
   - Загрузить `knowledge_os/dashboard/grafana_dashboard.json`

---

## 🔧 КОНКРЕТНЫЙ ПЛАН: ELK СТЕК

### Шаг 1: Добавить в docker-compose.yml

```yaml
services:
  # ... существующие сервисы ...

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: atra-elasticsearch
    environment:
      - discovery.type=single-node
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - xpack.security.enabled=false
      - xpack.security.enrollment.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    networks:
      - atra-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: atra-kibana
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - ELASTICSEARCH_USERNAME=kibana_system
      - ELASTICSEARCH_PASSWORD=
      - xpack.security.enabled=false
    networks:
      - atra-network
    depends_on:
      elasticsearch:
        condition: service_healthy
    restart: unless-stopped

volumes:
  # ... существующие volumes ...
  elasticsearch_data:
```

### Шаг 2: Создать ELKHandler

Создать `knowledge_os/app/elk_handler.py`:

```python
"""
ELK Handler для отправки логов в Elasticsearch
"""
import asyncio
import httpx
import json
import logging
from datetime import datetime
from typing import Optional

class ELKHandler(logging.Handler):
    """Handler для отправки логов в Elasticsearch"""
    
    def __init__(self, elasticsearch_url: str = "http://atra-elasticsearch:9200"):
        super().__init__()
        self.elasticsearch_url = elasticsearch_url
        self.index_prefix = "atra-logs"
        self.client: Optional[httpx.AsyncClient] = None
        self._init_client()
    
    def _init_client(self):
        """Инициализация HTTP клиента"""
        try:
            self.client = httpx.AsyncClient(timeout=5.0)
        except Exception as e:
            logging.error(f"Failed to init ELK client: {e}")
    
    def emit(self, record):
        """Отправка лога в Elasticsearch"""
        if not self.client:
            return
        
        try:
            log_data = {
                "@timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            # Добавляем дополнительные поля если есть
            if hasattr(record, 'extra'):
                log_data.update(record.extra)
            
            # Добавляем exception если есть
            if record.exc_info:
                log_data["exception"] = self.format(record)
            
            # Отправка в Elasticsearch (асинхронно, не блокирует)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._send_to_elasticsearch(log_data))
                else:
                    loop.run_until_complete(self._send_to_elasticsearch(log_data))
            except RuntimeError:
                # Нет event loop, создаем новый
                asyncio.run(self._send_to_elasticsearch(log_data))
        except Exception:
            self.handleError(record)
    
    async def _send_to_elasticsearch(self, log_data: dict):
        """Асинхронная отправка в Elasticsearch"""
        if not self.client:
            return
        
        try:
            index_name = f"{self.index_prefix}-{datetime.utcnow().strftime('%Y.%m.%d')}"
            url = f"{self.elasticsearch_url}/{index_name}/_doc"
            response = await self.client.post(url, json=log_data)
            response.raise_for_status()
        except Exception as e:
            # Fallback на файловое логирование при ошибке
            logging.debug(f"Failed to send log to Elasticsearch: {e}")
    
    def close(self):
        """Закрытие клиента"""
        if self.client:
            asyncio.run(self.client.aclose())
        super().close()
```

### Шаг 3: Интегрировать в логирование

Обновить `knowledge_os/src/shared/utils/logger.py`:

```python
def setup_logging(
    level: str = "INFO", 
    use_structlog: bool = True, 
    use_elk: bool = False,
    elk_url: Optional[str] = None
):
    """Setup structured logging with optional ELK integration"""
    # ... существующий код structlog ...
    
    if use_elk:
        try:
            import sys
            sys.path.insert(0, '/app')  # Путь в контейнере
            from app.elk_handler import ELKHandler
            
            elk_handler = ELKHandler(elk_url or "http://atra-elasticsearch:9200")
            elk_handler.setLevel(getattr(logging, level.upper()))
            
            # Добавляем к root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(elk_handler)
            
            logging.info("✅ ELK handler enabled")
        except ImportError as e:
            logging.warning(f"ELK handler not available: {e}")
        except Exception as e:
            logging.warning(f"Failed to setup ELK handler: {e}")
```

### Шаг 4: Включить в конфигурации

Добавить переменные окружения в `docker-compose.yml`:

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

knowledge_os_api:
  environment:
    # ... существующие переменные ...
    - USE_ELK=true
    - ELASTICSEARCH_URL=http://atra-elasticsearch:9200
```

### Шаг 5: Запустить

```bash
docker-compose -f knowledge_os/docker-compose.yml up -d elasticsearch kibana
```

### Шаг 6: Настроить Kibana

1. Открыть http://localhost:5601
2. Создать index pattern: `atra-logs-*`
3. Time field: `@timestamp`
4. Создать дашборды для анализа логов

---

## ✅ ПРЕИМУЩЕСТВА ПОСЛЕ РЕАЛИЗАЦИИ

### Grafana:
- 📊 Визуализация метрик производительности
- 📈 Дашборды для мониторинга корпорации
- 🚨 Алерты при проблемах
- 📉 Анализ трендов производительности

### ELK стек:
- 🔍 Централизованный поиск по логам всех компонентов
- 📊 Визуализация паттернов в логах
- 🚨 Алерты на основе логов
- 📈 Анализ производительности через логи

---

## 🎯 РЕКОМЕНДАЦИЯ

**Начать с Grafana + Prometheus** — быстро даст визуализацию метрик, которые уже собираются.

**Затем ELK стек** — для централизованного логирования и анализа.

**Оба компонента критичны для масштабирования корпорации ATRA!**

---

*План создан 2026-01-25*
