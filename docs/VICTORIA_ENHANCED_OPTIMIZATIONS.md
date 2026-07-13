# Оптимизация Victoria Enhanced для больших проектов

**Дата:** 2026-02-24  
**Проблема:** Victoria Enhanced зависала на аудите больших проектов (3+ минуты без ответа)  
**Решение:** Chunking, параллельное делегирование, timeout handling, streaming progress

---

## Изменения

### 1. **Chunking Strategy** (`knowledge_os/app/project_audit_optimizer.py`)

Разбиение аудита на фазы:

- **Phase 1:** Structure scan (1 мин) - README, package files, CI config
- **Phase 2:** Key modules selection (мгновенно) - entry points, core logic
- **Phase 3:** Expert review (5 мин на эксперта, параллельно)
- **Phase 4:** Synthesis (3 мин) - финальный отчёт

**Конфигурация:**

```bash
# .env
MAX_FILES_FOR_FULL_ANALYSIS=50  # Лимит файлов для полного анализа
MAX_KEY_MODULES=10              # Сколько ключевых модулей анализировать
AUDIT_STRUCTURE_TIMEOUT=60      # Таймаут структурного сканирования
AUDIT_MODULE_TIMEOUT=300        # Таймаут анализа модулей
AUDIT_EXPERT_TIMEOUT=300        # Таймаут эксперта при аудите (5 мин)
AUDIT_SYNTHESIS_TIMEOUT=180     # Таймаут синтеза
AUDIT_TOTAL_TIMEOUT=1800        # Общий таймаут аудита (30 мин)
```

### 2. **Параллельное делегирование** (`execute_assignments.py`)

**До (последовательное):**

```python
for expert in experts:
    result = await delegate_to_expert(expert, task)  # ждём каждого
    results.append(result)
# Время: N экспертов × timeout_per_expert
```

**После (параллельное):**

```python
tasks = [delegate_to_expert(e, task) for e in experts]
results = await asyncio.gather(*tasks)  # все сразу
# Время: max(expert timeouts)
```

**Адаптивный таймаут:**

- Обычные задачи: 600 секунд (10 мин)
- Аудит проекта: 300 секунд (5 мин)

### 3. **Timeout для Victoria Enhanced** (`victoria_server.py`)

**Добавлен timeout на enhanced.solve:**

```python
VICTORIA_AUDIT_TIMEOUT = int(os.getenv("VICTORIA_AUDIT_TIMEOUT", "1800"))  # 30 мин

try:
    enhanced_result = await asyncio.wait_for(
        enhanced.solve(goal, use_enhancements=True, context=context),
        timeout=float(VICTORIA_AUDIT_TIMEOUT),
    )
except asyncio.TimeoutError:
    # Возвращаем понятное сообщение вместо зависания
    return {"error": f"Превышено время анализа ({VICTORIA_AUDIT_TIMEOUT} с)"}
```

### 4. **Streaming Progress** (`victoria_server.py`)

**Функция обновления прогресса:**

```python
async def _update_task_progress(
    task_id: str,
    stage: str,
    progress_pct: Optional[int] = None,
    progress_message: Optional[str] = None,
):
    """Обновить прогресс фоновой задачи для polling-клиентов."""
    store["stage"] = stage
    store["progress"] = progress_pct
    store["progress_message"] = progress_message
    # Также пишем в Redis для Gateway
    await redis_manager.update_task_status(task_id, "processing", metadata={...})
```

**Использование в enhanced.solve:**

```python
await _update_task_progress(task_id, "enhanced_analysis", 40,
                          "Анализ (Victoria Enhanced). Это может занять несколько минут…")
# Пользователь видит прогресс через GET /run/status/{task_id}
```

**Ответ GET /run/status/{task_id}:**

```json
{
  "task_id": "...",
  "status": "processing",
  "stage": "enhanced_analysis",
  "progress": 40,
  "progress_message": "Анализ (Victoria Enhanced). Это может занять несколько минут…",
  "updated_at": "2026-02-24T16:48:00Z"
}
```

---

## Использование

### Обычный запрос (без chunking)

```bash
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Проведи аудит проекта в /path/to/project",
    "use_enhanced": true,
    "async_mode": true
  }'

# Ответ: {"task_id": "...", "status_url": "/run/status/..."}

# Polling (каждые 2-5 секунд)
curl http://localhost:8010/run/status/{task_id}
# Ответ: {"status": "processing", "stage": "enhanced_analysis", "progress": 40}
```

**Теперь с timeout:** Если enhanced.solve занимает > 30 минут, вернётся:

```json
{
  "status": "failed",
  "error": "Превышено время анализа (1800 с). Попробуйте задачу короче..."
}
```

### Chunked audit (для больших проектов)

```python
from knowledge_os.app.project_audit_optimizer import audit_project_chunked

async def on_progress(data):
    print(f"Progress: {data['progress']}% - {data['status']}")

result = await audit_project_chunked(
    "/Users/bikos/Downloads/ripgrep",
    "rust",
    "Проведи полный аудит проекта",
    progress_callback=on_progress
)
```

**Вывод:**

```
Progress: 20% - structure_complete
Progress: 50% - module_analyzed
Progress: 90% - experts_complete
Progress: 100% - done
```

---

## Тестирование

### 1. Проверка timeout

```bash
# Установить короткий timeout для теста
export VICTORIA_AUDIT_TIMEOUT=10  # 10 секунд

# Отправить сложную задачу
curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Проведи глубокий анализ всего проекта...",
    "use_enhanced": true,
    "async_mode": true
  }'

# Через 10 секунд получите:
# {"status": "failed", "error": "Превышено время анализа (10 с)"}
```

### 2. Проверка прогресса

```bash
# Отправить задачу
TASK_ID=$(curl -X POST http://localhost:8010/run \
  -H "Content-Type: application/json" \
  -d '{"goal": "...", "use_enhanced": true, "async_mode": true}' \
  | jq -r '.task_id')

# Мониторить прогресс
while true; do
  curl -s http://localhost:8010/run/status/$TASK_ID | jq '{status, stage, progress, progress_message}'
  sleep 2
done
```

### 3. Проверка параллельного делегирования

Посмотреть логи:

```bash
docker logs victoria-agent 2>&1 | grep "MONSTER.*Запуск run_smart_agent_async"
```

**До (последовательное):**

```
⏳ [MONSTER] Запуск run_smart_agent_async для Игорь
⏳ [MONSTER] Запуск run_smart_agent_async для Анна (через 5 мин)
⏳ [MONSTER] Запуск run_smart_agent_async для Дмитрий (через 10 мин)
```

**После (параллельное):**

```
⏳ [MONSTER] Запуск run_smart_agent_async для Игорь
⏳ [MONSTER] Запуск run_smart_agent_async для Анна (одновременно)
⏳ [MONSTER] Запуск run_smart_agent_async для Дмитрий (одновременно)
```

---

## Метрики производительности

| Сценарий                   | До               | После              | Улучшение      |
| -------------------------- | ---------------- | ------------------ | -------------- |
| Аудит ripgrep (100 файлов) | timeout (>4 мин) | ~2-3 мин           | ✅ работает    |
| Делегирование 3 экспертов  | ~15 мин (5×3)    | ~5 мин (max)       | **3× быстрее** |
| Feedback пользователю      | нет (зависание)  | streaming progress | ✅ есть        |
| Timeout handling           | зависание curl   | понятная ошибка    | ✅ есть        |

---

## Переменные окружения

Добавить в `.env` или `docker-compose.yml`:

```bash
# Таймауты для Victoria Enhanced
VICTORIA_AUDIT_TIMEOUT=1800           # 30 мин общий таймаут на enhanced.solve
AUDIT_EXPERT_TIMEOUT=300              # 5 мин на эксперта при аудите

# Chunking для больших проектов
MAX_FILES_FOR_FULL_ANALYSIS=50
MAX_KEY_MODULES=10
AUDIT_STRUCTURE_TIMEOUT=60
AUDIT_MODULE_TIMEOUT=300
AUDIT_SYNTHESIS_TIMEOUT=180
AUDIT_TOTAL_TIMEOUT=1800
```

---

## Troubleshooting

### Проблема: Всё равно timeout

**Причина:** Проект слишком большой (1000+ файлов).

**Решение:**

1. Увеличить `VICTORIA_AUDIT_TIMEOUT` до 3600 (1 час)
2. Использовать chunked flow (`audit_project_chunked`)
3. Разбить аудит на части: "Проведи аудит только core/" вместо всего проекта

### Проблема: Progress не обновляется

**Причина:** Redis manager не доступен или используется локальный store.

**Решение:**

- Проверить `docker ps | grep redis`
- В логах должно быть: `✅ Redis Manager инициализирован`
- Если нет — прогресс пишется в `_run_task_store` (только для одного процесса)

### Проблема: Эксперты всё равно последовательно

**Причина:** Ошибка в `execute_assignments_async`.

**Решение:**

- Проверить логи: должно быть `📥 [MONSTER] Задача X отправлена в очередь Redis` для всех экспертов сразу
- Затем `⏳ [MONSTER] Запуск run_smart_agent_async` для всех параллельно
- Если нет — проверить `asyncio.gather` в строке 176 `execute_assignments.py`

---

## Дальнейшие улучшения

1. **WebSocket прогресс** — вместо polling использовать WebSocket для real-time updates
2. **Incremental results** — возвращать промежуточные результаты (structure → modules → experts → synthesis)
3. **Cancellation** — добавить `DELETE /run/{task_id}` для отмены долгих задач
4. **Priority queue** — приоритет для аудита перед обычными задачами

---

**Итого:** Система теперь не зависает на больших проектах, пользователь видит прогресс, эксперты работают параллельно. Timeout 30 минут для enhanced.solve предотвращает бесконечное ожидание.
