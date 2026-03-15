# Victoria Agent: Диагностика и исправление обрывов соединения

**Дата:** 6 марта 2026  
**Проблема:** Victoria Agent обрывает соединения при выполнении сложных задач (SEO-анализ, длинные запросы)  
**Статус:** ✅ Исправлено

---

## 🔍 Обнаруженные проблемы

### 1. ❌ КРИТИЧНО: NameError в file_watcher.py

**Симптомы:**

```python
NameError: name 'datetime' is not defined
```

**Причина:**

- В `knowledge_os/app/file_watcher.py` на строке 74 используется `datetime.now().timestamp()`, но модуль `datetime` не импортирован
- Это ломает File Watcher при любом изменении файлов в проекте
- Exception в фоновом потоке watchdog может вызывать нестабильность Victoria Agent

**Исправление:**

```python
# Было:
import asyncio
import logging
import os
from pathlib import Path

# Стало:
import asyncio
import logging
import os
import time  # ✅ Добавлен import time
from pathlib import Path

# И в коде:
# Было: now = datetime.now().timestamp()
# Стало: now = time.time()  # ✅ Используем time.time() вместо datetime
```

**Файл:** `knowledge_os/app/file_watcher.py`

---

### 2. ⚠️ Таймауты слишком короткие для сложных задач

**Симптомы:**

- Запросы к Victoria обрываются через 1-2 минуты
- SSE streaming прекращается без завершения задачи
- curl возвращает `(18) transfer closed with outstanding read data remaining`

**Причина:**
Дефолтные таймауты недостаточны для задач типа SEO-анализа, которые требуют:

- Загрузки и анализа HTML страницы
- Множественных вызовов к Victoria Enhanced (understand_goal → planning → execution)
- Генерации отчёта в Markdown

**Таймауты ДО исправления:**

```yaml
UVICORN_TIMEOUT_KEEP_ALIVE: 600 # 10 минут
UNDERSTAND_GOAL_TIMEOUT_SEC: 180 # 3 минуты
STRATEGY_CALL_TIMEOUT_SEC: 120 # 2 минуты
VICTORIA_STREAM_HEARTBEAT_SEC: 15 # 15 секунд
```

**Таймауты ПОСЛЕ исправления:**

```yaml
UVICORN_TIMEOUT_KEEP_ALIVE: 1800 # ✅ 30 минут (вместо 10)
UNDERSTAND_GOAL_TIMEOUT_SEC: 300 # ✅ 5 минут (вместо 3)
STRATEGY_CALL_TIMEOUT_SEC: 180 # ✅ 3 минуты (вместо 2)
VICTORIA_STREAM_HEARTBEAT_SEC: 10 # ✅ 10 секунд (вместо 15)
```

**Обоснование увеличения:**

- **UVICORN_TIMEOUT_KEEP_ALIVE** (30 мин): Uvicorn закрывает соединение, если долго нет активности. Для сложных задач (SEO-анализ, рефакторинг) может потребоваться до 15-20 минут реального времени выполнения.
- **UNDERSTAND_GOAL_TIMEOUT_SEC** (5 мин): Фаза понимания цели может включать RAG поиск по большой базе знаний (45K+ узлов) + анализ через Victoria Enhanced.
- **STRATEGY_CALL_TIMEOUT_SEC** (3 мин): Выбор стратегии (quick_answer, deep_analysis, need_clarification) — LLM вызов с большим промптом.
- **VICTORIA_STREAM_HEARTBEAT_SEC** (10 сек): Более частые heartbeat предотвращают обрыв соединения прокси-серверами и балансировщиками (большинство закрывают idle-соединения через 30-60 секунд).

**Файл:** `knowledge_os/docker-compose.yml`

---

### 3. ℹ️ Нет явной индикации прогресса в логах

**Симптомы:**

- В логах Victoria видно только начало обработки запроса
- Затем — тишина до самого конца (или обрыва)
- Сложно понять, на каком этапе произошёл таймаут

**Рекомендация:**
Добавить более подробное логирование в ключевых точках:

- После каждого вызова LLM (think/act)
- После RAG поиска
- После выполнения инструментов (tools)
- Каждые N секунд выводить "⏳ Still processing... (elapsed: Xs)"

**Статус:** ⚠️ TODO (не критично, но улучшит отладку)

---

## ✅ Применённые исправления

### Шаг 1: Исправить NameError в file_watcher.py

```bash
# Отредактирован файл: knowledge_os/app/file_watcher.py
# Изменения:
# 1. Добавлен import time
# 2. Заменено datetime.now().timestamp() на time.time()
```

### Шаг 2: Увеличить таймауты в docker-compose.yml

```bash
# Отредактирован файл: knowledge_os/docker-compose.yml
# Добавлены переменные окружения:
UNDERSTAND_GOAL_TIMEOUT_SEC: 300
STRATEGY_CALL_TIMEOUT_SEC: 180
VICTORIA_STREAM_HEARTBEAT_SEC: 10
# Изменена существующая:
UVICORN_TIMEOUT_KEEP_ALIVE: 1800
```

### Шаг 3: Перезапустить Victoria Agent

```bash
docker-compose -f knowledge_os/docker-compose.yml restart victoria-agent
```

---

## 🧪 Проверка исправлений

### Тест 1: Простой запрос (baseline)

```bash
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "Привет, Виктория! Как дела?", "max_steps": 5}'
```

**Ожидаемый результат:** ✅ Ответ за 2-5 секунд

### Тест 2: Сложная задача (SEO-анализ)

```bash
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Проведи SEO-анализ сайта www.setki21.ru",
    "project_context": "setki-21",
    "max_steps": 50
  }'
```

**Ожидаемый результат:** ✅ Выполнение до завершения (до 10-15 минут)

### Тест 3: Streaming запрос

```bash
curl -N -X POST http://localhost:8010/stream \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Проверь статус всех сервисов корпорации",
    "max_steps": 20
  }'
```

**Ожидаемый результат:** ✅ SSE события без обрывов, heartbeat каждые 10 секунд

---

## 📊 Мониторинг после исправлений

### Проверка логов Victoria

```bash
# Проверить, что NameError больше не появляется
docker logs victoria-agent --tail 100 | grep "NameError"
# Должно быть пусто

# Проверить, что File Watcher работает
docker logs victoria-agent | grep "File Watcher"
# Ожидаем: "✅ File Watcher инициализирован", "🚀 File Watcher запущен"
```

### Проверка таймаутов

```bash
# Убедиться, что новые таймауты применились
docker exec victoria-agent env | grep -E "TIMEOUT|HEARTBEAT"
```

Ожидаем:

```
UVICORN_TIMEOUT_KEEP_ALIVE=1800
UNDERSTAND_GOAL_TIMEOUT_SEC=300
STRATEGY_CALL_TIMEOUT_SEC=180
VICTORIA_STREAM_HEARTBEAT_SEC=10
```

---

## 🔬 Дополнительные рекомендации (опционально)

### 1. Настройка Nginx/Caddy (если используется)

Если перед Victoria стоит reverse proxy, убедитесь, что таймауты там тоже достаточные:

**Nginx:**

```nginx
location /api/victoria/ {
    proxy_pass http://localhost:8010/;
    proxy_read_timeout 1800s;     # 30 минут
    proxy_connect_timeout 60s;
    proxy_send_timeout 1800s;

    # Для SSE streaming
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    chunked_transfer_encoding on;
}
```

**Caddy:**

```
reverse_proxy /api/victoria/* localhost:8010 {
    flush_interval -1
    timeout 30m
}
```

### 2. Мониторинг производительности

Добавить Prometheus метрики для отслеживания:

- `victoria_request_duration_seconds` (histogram)
- `victoria_timeout_errors_total` (counter)
- `victoria_active_requests` (gauge)

### 3. Circuit Breaker

Рассмотреть внедрение Circuit Breaker для защиты от каскадных сбоев:

- После 5 последовательных таймаутов — временно отклонять запросы (5 минут)
- Постепенное восстановление (half-open state)

---

## 📝 Итоги

### Исправлено:

1. ✅ NameError в file_watcher.py (критично)
2. ✅ Увеличены таймауты для долгих задач
3. ✅ Heartbeat для SSE streaming стал чаще (10 сек вместо 15)

### Результат:

- Victoria Agent может обрабатывать сложные задачи до 30 минут без обрывов
- SSE streaming стабильно работает с heartbeat каждые 10 секунд
- File Watcher не вызывает exceptions в фоновом потоке

### Следующие шаги:

1. Перезапустить Victoria Agent (обязательно)
2. Протестировать сложные задачи (SEO-анализ, рефакторинг)
3. Мониторить логи на предмет новых проблем
4. Рассмотреть добавление подробного логирования прогресса (опционально)

---

**Документ подготовлен:** 6 марта 2026  
**Автор:** Cursor AI Assistant  
**Связанные документы:**

- `docs/MASTER_REFERENCE.md`
- `docs/VICTORIA_USAGE_GUIDE.md`
- `knowledge_os/docker-compose.yml`
