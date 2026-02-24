# 📊 Мониторинг MLX API Server

Документация по просмотру метрик и загрузки MLX API Server.

---

## 🚀 Быстрый просмотр

### Через скрипт (рекомендуется):

```bash
bash scripts/check_mlx_status.sh
```

### Через curl:

```bash
# Прямой доступ к MLX
curl http://localhost:11435/health | python3 -m json.tool

# Через backend API
curl http://localhost:8080/api/chat/mlx/metrics | python3 -m json.tool
```

---

## 📈 Основные метрики

### 1. **Статус сервера**

- `status`: `"healthy"` | `"degraded"` | `"warning"` | `"critical"`
- `service`: Название сервиса
- `version`: Версия API

### 2. **Загрузка запросами**

- `active_requests`: Текущее количество активных запросов
- `max_concurrent`: Максимальное количество параллельных запросов (по умолчанию: 5)
- `active_model_requests`: Запросы по каждой модели

**Пример:**

```json
{
  "active_requests": 2,
  "max_concurrent": 5,
  "active_model_requests": {
    "qwen2.5-coder:32b": 1,
    "phi3.5:3.8b": 1
  }
}
```

### 3. **Использование памяти**

- `memory.used_percent`: Процент использования памяти (0-100)
- `memory.available_gb`: Доступная память в GB
- `memory.total_gb`: Общий объем памяти в GB
- `memory.warning_threshold`: Порог предупреждения (по умолчанию: 85%)
- `memory.critical_threshold`: Критический порог (по умолчанию: 95%)

**Пример:**

```json
{
  "memory": {
    "used_percent": 45.2,
    "available_gb": 32.5,
    "total_gb": 64.0,
    "warning_threshold": 85.0,
    "critical_threshold": 95.0
  }
}
```

### 4. **Загруженные модели**

- `models_cached`: Количество моделей в кэше
- `cached_models`: Список загруженных моделей с метриками:
  - `name`: Имя модели
  - `use_count`: Количество использований
  - `last_used`: Время последнего использования
  - `load_time_seconds`: Время загрузки модели
  - `active_requests`: Активные запросы к этой модели
  - `is_loading`: Загружается ли модель сейчас

**Пример:**

```json
{
  "models_cached": 3,
  "cached_models": [
    {
      "name": "qwen2.5-coder:32b",
      "use_count": 15,
      "last_used": "2026-01-26T21:30:00.000000",
      "load_time_seconds": 5.48,
      "active_requests": 1,
      "is_loading": false
    }
  ]
}
```

### 5. **Rate Limiting**

- `rate_limit.max_per_window`: Максимум запросов в окне
- `rate_limit.window_seconds`: Размер окна в секундах

### 6. **Предупреждения**

- `warnings`: Список предупреждений (высокое использование памяти, перегрузка запросами)

---

## 🔍 Интерпретация статусов

### `healthy`

- ✅ Память < 85%
- ✅ Активных запросов < максимума
- ✅ Все модели работают нормально

### `degraded`

- ⚠️ Память 85-95% ИЛИ
- ⚠️ Активных запросов = максимуму
- ⚠️ Сервер работает, но перегружен

### `warning`

- ⚠️ Память 85-95%
- ⚠️ Есть предупреждения

### `critical`

- 🚨 Память > 95%
- 🚨 Критическая ситуация
- 🚨 Автоматическая очистка моделей

---

## 📊 Примеры использования

### Проверка загрузки:

```bash
# Быстрая проверка статуса
curl -s http://localhost:11435/health | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"Статус: {d['status']}\"); print(f\"Активных запросов: {d['active_requests']}/{d['max_concurrent']}\"); print(f\"Память: {d['memory']['used_percent']}%\")"
```

### Мониторинг в реальном времени:

```bash
watch -n 2 'curl -s http://localhost:11435/health | python3 -m json.tool | grep -A 5 "active_requests\|memory"'
```

### Проверка конкретной модели:

```bash
curl -s http://localhost:11435/health | python3 -c "import sys, json; d=json.load(sys.stdin); models=[m for m in d['cached_models'] if m['name']=='qwen2.5-coder:32b']; print(json.dumps(models[0] if models else {}, indent=2))"
```

---

## 🛠️ Endpoints

### MLX API Server (прямой доступ):

- `GET /health` - Полные метрики и статус

### Backend API (через ATRA Web IDE):

- `GET /api/chat/mlx/metrics` - Проксирует метрики MLX
- `GET /api/chat/status` - Статус Victoria и MLX

---

## 💡 Рекомендации

1. **Мониторинг памяти:**
   - При > 85% - предупреждение
   - При > 95% - автоматическая очистка неиспользуемых моделей

2. **Параллельные запросы:**
   - Максимум: 5 одновременных запросов
   - При достижении лимита - новые запросы отклоняются

3. **Оптимизация:**
   - Неиспользуемые модели автоматически выгружаются
   - LRU (Least Recently Used) алгоритм для кэша моделей

---

_Обновлено: 26.01.2026_
