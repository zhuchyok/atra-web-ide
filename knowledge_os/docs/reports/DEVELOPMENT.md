# 🚀 ATRA Trading Bot - Development Guide

## 📋 Архитектурные решения и стандарты кода

### 🛡️ Exception Handling

**Принцип:** Используем специфичные типы исключений в бизнес-логике, широкий `Exception` только для защиты main loop.

**Примеры:**

```python
# ✅ Правильно - специфичные исключения
except (ValueError, TypeError, KeyError, ConnectionError) as e:
    logger.error("Ошибка: %s", e)

# ✅ Правильно - защита main loop
except Exception as e:
    logger.critical("Критическая ошибка: %s", e, exc_info=True)
    # Алерт админу и fallback
```

**Кастомные исключения:**

- `SignalValidationError` - ошибки валидации сигналов
- `DataQualityError` - проблемы с качеством данных
- `DatabaseConnectionError` - ошибки БД
- `APIError` - ошибки внешних API

### 🏗️ Singleton Pattern

**Принцип:** Используем классический singleton через `__new__` для подключения к БД.

```python
class DatabaseSingleton(Database):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### 📦 Опциональные модули

**Принцип:** Используем try/except для опциональных импортов.

```python
try:
    import backtest_integration
    BACKTEST_ENABLED = True
except ImportError:
    BACKTEST_ENABLED = False
```

### 📊 Логирование

**Принцип:** Structured logging с метаданными для мониторинга.

```python
logger.info("Signal sent", extra={
    "user_id": user_id,
    "symbol": symbol,
    "trace_id": trace_id,
    "ai_confidence": confidence
})
```

### 🔧 Настройка линтера

**pylint:** Отключаем предупреждения для production-кода:

- `broad-except` - для защиты main loop
- `global-statement` - для singleton pattern
- `import-error` - для опциональных модулей

**flake8:** Настраиваем под реальность:

- `E722` - разрешаем `except Exception:`
- `max-complexity = 12` - разумный лимит сложности
- `max-line-length = 120` - современный стандарт

### 🧪 Тестирование

**Покрытие:** Все критические функции и интеграции
**Инструменты:** pytest + coverage + flake8 в CI
**Тесты:** Обработка ошибок, поведение singleton, опциональные модули

### 📈 Мониторинг

**Метрики:** Производительность, latency, error rate
**Health checks:** БД, API, очереди, AI
**Алерты:** Задержки, массовые ошибки, переполнение очереди

### 🚨 Алерты и уведомления

**Критические ошибки:** Логирование + алерт админу
**Fallback:** Graceful degradation при сбоях
**Trace ID:** Для отслеживания запросов

---

## 📚 Дополнительные ресурсы

- [PEP 8 - Style Guide](https://pep8.org/)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [Exception Handling in Python](https://docs.python.org/3/tutorial/errors.html)
- [Singleton Pattern in Python](https://python-patterns.guide/gang-of-four/singleton/)

---

**Последнее обновление:** 2025-10-19
**Версия:** 1.0.0
