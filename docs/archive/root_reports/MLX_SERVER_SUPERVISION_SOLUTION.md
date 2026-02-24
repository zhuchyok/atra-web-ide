# 🔧 Решение проблемы падения MLX Server: Supervision Pattern

## ❌ Проблема

MLX API Server падает во время выполнения задач, особенно при:

- Параллельных запросах от сотрудников
- Синтезе результатов Victoria
- Высокой нагрузке

**Последствия:**

- Использование fallback Ollama (некорректные результаты)
- Потеря предзагруженных моделей
- Необходимость ручного перезапуска

## ✅ Решение: Supervision Pattern (мировые практики)

### 1. **Elixir-Style Supervision Tree**

**Принцип:** Автоматический перезапуск процесса при падении с rate limiting.

**Реализация:**

- `MLXServerSupervisor` - supervisor для MLX API Server
- Автоматический перезапуск при обнаружении падения
- Rate limiting: максимум 5 перезапусков за 5 минут
- Отслеживание состояния процесса

### 2. **Exponential Backoff**

**Принцип:** Постепенное увеличение задержки между перезапусками.

**Реализация:**

- Начальная задержка: 2 секунды
- Максимальная задержка: 60 секунд
- Формула: `delay = min(2 * 2^n, 60)` где n - количество перезапусков

**Преимущества:**

- Предотвращает бесконечные циклы перезапуска
- Дает время системе восстановиться
- Снижает нагрузку на систему

### 3. **Circuit Breaker Pattern**

**Принцип:** Защита от каскадных сбоев.

**Реализация:**

- Интеграция с `CircuitBreaker` из `circuit_breaker.py`
- После 5 неудачных перезапусков → Circuit OPEN
- Блокировка перезапусков на 60 секунд
- Автоматический переход в HALF_OPEN для тестирования

**Состояния:**

- **CLOSED**: Нормальная работа, перезапуски разрешены
- **OPEN**: Слишком много ошибок, перезапуски заблокированы
- **HALF_OPEN**: Тестирование восстановления

### 4. **Health Monitoring**

**Принцип:** Постоянная проверка здоровья сервера.

**Реализация:**

- Health check каждые 10 секунд
- Проверка `/health` endpoint
- После 3 неудачных проверок → сервер считается упавшим
- Автоматический перезапуск при обнаружении падения

### 5. **Graceful Shutdown**

**Принцип:** Корректное завершение процесса.

**Реализация:**

- Отправка SIGTERM для graceful shutdown
- Ожидание завершения (до 10 секунд)
- Принудительная остановка (SIGKILL) при таймауте
- Очистка ресурсов (модели, соединения)

## 📊 Архитектура

```
MLXServerSupervisor
├── Process Management
│   ├── Start Server
│   ├── Stop Server (graceful)
│   └── Monitor Process
├── Health Monitoring
│   ├── Health Check Loop (10s)
│   ├── Failure Detection (3 failures)
│   └── Status Tracking
├── Restart Logic
│   ├── Rate Limiting (5 restarts / 5min)
│   ├── Exponential Backoff (2s → 60s)
│   └── State Management
└── Circuit Breaker
    ├── Failure Tracking
    ├── State Transitions
    └── Recovery Testing
```

## 🚀 Использование

### Запуск с Supervisor:

```bash
# Стандартный запуск (с supervisor)
python3 scripts/start_mlx_with_supervisor.py

# Или через wrapper скрипт
./scripts/start_mlx_server.sh
```

### Интеграция с ServiceMonitor:

```python
from app.service_monitor import ServiceMonitor, Service
from app.mlx_server_supervisor import get_mlx_supervisor

# ServiceMonitor уже мониторит MLX Server
# Supervisor автоматически перезапускает при падении
```

### Программное использование:

```python
from app.mlx_server_supervisor import get_mlx_supervisor

supervisor = get_mlx_supervisor()

# Запуск
await supervisor.start()

# Получение статуса
status = supervisor.get_status()
print(f"State: {status['state']}, Restarts: {status['restart_count']}")

# Остановка
await supervisor.stop()
```

## 📈 Преимущества

1. **Автоматическое восстановление** - сервер перезапускается автоматически
2. **Защита от каскадных сбоев** - Circuit Breaker предотвращает бесконечные перезапуски
3. **Оптимизация ресурсов** - Exponential backoff снижает нагрузку
4. **Мониторинг** - постоянная проверка здоровья
5. **Graceful shutdown** - корректное завершение без потери данных

## 🔍 Мониторинг

### Статус supervisor:

```python
status = supervisor.get_status()
# {
#   "state": "running",
#   "process_pid": 12345,
#   "restart_count": 0,
#   "health_check_failures": 0,
#   "circuit_breaker_state": "closed"
# }
```

### Логи:

```
✅ [SUPERVISOR] MLX API Server запущен и здоров (PID: 12345)
🔍 [SUPERVISOR] Запущен цикл мониторинга
⚠️ [SUPERVISOR] Health check failed (1/3)
❌ [SUPERVISOR] Сервер упал (код: 1)
🔄 [SUPERVISOR] Попытка перезапуска сервера...
⏳ [SUPERVISOR] Ожидание 2.0с перед перезапуском (exponential backoff)
✅ [SUPERVISOR] MLX API Server запущен и здоров (PID: 12346)
```

## 🌍 Мировые практики

### 1. **Elixir/OTP Supervision Trees**

- Иерархическая структура процессов
- Автоматический перезапуск при падении
- Стратегии перезапуска (one-for-one, one-for-all)

### 2. **Akka Supervision (Scala)**

- Actor-based supervision
- Restart strategies
- Backoff supervisors

### 3. **Kubernetes Pod Restart Policies**

- Always, OnFailure, Never
- Restart limits
- Exponential backoff

### 4. **Systemd Service Management**

- Restart policies
- Restart limits
- Restart delays

## ✅ Результат

MLX API Server теперь:

- ✅ Автоматически перезапускается при падении
- ✅ Защищен от каскадных сбоев (Circuit Breaker)
- ✅ Использует exponential backoff для оптимизации
- ✅ Постоянно мониторится на здоровье
- ✅ Корректно завершается (graceful shutdown)

**Сервер готов к production использованию!** 🎉
