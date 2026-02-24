# 📊 OpenTelemetry Setup для ATRA Enhanced

**Дата:** 2026-01-25  
**Версия:** 1.0

---

## 🎯 Обзор

OpenTelemetry интеграция для трассировки и мониторинга работы Victoria Enhanced и всех компонентов супер-корпорации.

---

## 📦 Установка

### 1. Установка зависимостей

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

### 2. Для HTTP трассировки (Ollama запросы)

```bash
pip install opentelemetry-instrumentation-httpx
```

### 3. Для Jaeger (опционально)

```bash
pip install opentelemetry-exporter-jaeger
```

---

## ⚙️ Настройка

### Переменные окружения

```bash
# Включить OpenTelemetry
export ENABLE_OTEL=true

# OTLP endpoint (для Jaeger, Tempo и т.д.)
export OTLP_ENDPOINT=http://localhost:4317

# Использовать insecure соединение (для dev)
export OTLP_INSECURE=true

# Имя сервиса
export OTEL_SERVICE_NAME=atra-enhanced
```

### В docker-compose.yml

```yaml
environment:
  ENABLE_OTEL: "true"
  OTLP_ENDPOINT: "http://jaeger:4317"
  OTLP_INSECURE: "true"
  OTEL_SERVICE_NAME: "victoria-enhanced"
```

---

## 🚀 Использование

### Автоматическая трассировка

Victoria Enhanced автоматически создает spans для:

- `victoria_enhanced.solve` - основная функция решения задач
- Категория задачи
- Выбранный метод
- Результат выполнения

### Ручная трассировка

```python
from app.observability import trace_span, get_observability_manager

# Контекстный менеджер
with trace_span("my_operation", {"key": "value"}):
    # Ваш код
    pass

# Декоратор
@trace_function("my_function")
async def my_function():
    pass

# Добавление событий
manager = get_observability_manager()
manager.add_event("important_event", {"data": "value"})
manager.set_attribute("custom.attribute", "value")
```

---

## 📊 Визуализация

### Jaeger

1. Запустить Jaeger:

```bash
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one:latest
```

2. Открыть UI: http://localhost:16686

### Grafana Tempo

1. Настроить Tempo в docker-compose.yml
2. Подключить Grafana к Tempo
3. Создать dashboard для трассировок

---

## 🔍 Атрибуты и метрики

### Автоматические атрибуты:

- `task.category` - категория задачи (reasoning, planning, complex, execution)
- `task.method` - выбранный метод (extended_thinking, tree_of_thoughts, swarm, etc.)
- `result.method` - фактический использованный метод
- `function.duration` - время выполнения функции
- `function.success` - успешность выполнения

### События:

- `task.completed` - задача завершена
- `method.selected` - метод выбран
- `error.occurred` - произошла ошибка

---

## 📈 Метрики производительности

### Измеряемые метрики:

1. **Latency** - время выполнения задач
2. **Throughput** - количество задач в секунду
3. **Error Rate** - процент ошибок
4. **Method Distribution** - распределение использования методов
5. **Category Distribution** - распределение категорий задач

---

## 🐛 Отладка

### Проверка работы:

```python
from app.observability import get_observability_manager

manager = get_observability_manager()
print(f"Enabled: {manager.enabled}")
print(f"Tracer: {manager.tracer is not None}")
```

### Логи:

```bash
# Включить детальное логирование
export LOG_LEVEL=DEBUG

# Проверить spans в консоли (если включен ConsoleSpanExporter)
```

---

## 🔧 Интеграция с Prometheus

OpenTelemetry может экспортировать метрики в Prometheus:

```python
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider

# Настройка Prometheus exporter
```

---

## 📚 Дополнительные ресурсы

- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [Grafana Tempo](https://grafana.com/docs/tempo/latest/)

---

**Обновлено:** 2026-01-25
