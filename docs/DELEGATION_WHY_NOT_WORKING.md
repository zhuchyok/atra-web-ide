# Почему делегирование Victoria → Veronica не срабатывает

Документ описывает **цепочку делегирования** и типичные причины, по которым задача не уходит в Veronica.

---

## Как устроено делегирование

1. **Кто решает:** В `run_task` и в `_run_task_background` тип задачи определяется через `detect_task_type(goal)`. Если тип **`veronica`** и включён Enhanced (`use_enhanced_for_request` / `use_enhanced_actual`), вызывается **`delegate_to_veronica(goal, project_context, correlation_id, max_steps)`**.

2. **Куда идёт запрос:** HTTP `POST {VERONICA_URL}/run` с телом `{"goal": "...", "project_context": "...", "max_steps": ...}`. Таймаут — `DELEGATE_VERONICA_TIMEOUT` (по умолчанию 60 с).

3. **Когда считаем успехом:** Ответ Veronica с HTTP 200 и в теле `status == "success"`. Тогда Victoria отдаёт пользователю ответ Veronica и в `knowledge` ставит `delegated_to: "Veronica"`, `routed_to: "veronica"`.

4. **Когда считаем провалом:** Исключение при запросе, HTTP ≠ 200 или отсутствие ответа. Тогда `veronica_tried_and_failed = True`, и задача выполняется через Victoria Enhanced или `agent.run()` (Victoria сама).

---

## Типичные причины «делегирование не срабатывает»

### 1. Veronica не вызывается (задача всегда идёт в Victoria)

- **Причина:** В **фоновом режиме** (async_mode, чат) делегирование раньше не вызывалось — только в синхронном `run_task`.  
  **Исправлено:** В `_run_task_background` добавлен тот же блок: при `task_type == "veronica"` сначала вызывается `delegate_to_veronica`, при успехе результат пишется в store и возврат; иначе — fallback на Enhanced / agent.run.

- **Проверка:** В логах Victoria при задаче типа «покажи файлы» / «выполни» должно быть:  
  `[DELEGATION] VERONICA_URL=...` и `Делегирую Veronica: ... -> http://...`.

### 2. Неверный VERONICA_URL

- **В Docker:** Victoria и Veronica в одном `docker-compose`. У сервиса **victoria-agent** в `environment` должно быть:  
  `VERONICA_URL: http://veronica-agent:8000`  
  (внутри сети контейнеры общаются по имени сервиса и внутреннему порту 8000.)

- **Локально (без Docker):** Оба процесса на одной машине:  
  `VERONICA_URL=http://localhost:8011`  
  (внешний порт Veronica — 8011.)

- **Victoria в Docker, Veronica на хосте:** Нужен URL хоста, например:  
  `VERONICA_URL=http://host.docker.internal:8011`  
  (для Mac/Windows; на Linux — IP хоста или `host.docker.internal` при настроенном extra_hosts.)

- **Проверка:** При первом делегировании в логах Victoria пишется:  
  `[DELEGATION] VERONICA_URL=...`  
  Убедитесь, что этот URL доступен из контейнера/процесса Victoria (например, `curl` или тест из кода).

### 3. Veronica не запущена или не в той же сети

- Контейнер: `docker ps | grep veronica-agent`.  
- Сеть: оба сервиса в одном `docker-compose` и в одной сети (например, `atra-network`).  
- Health: `curl -s http://localhost:8011/health` (с хоста) или из контейнера Victoria:  
  `curl -s http://veronica-agent:8000/health`.

### 4. Таймаут / сеть

- При долгом ответе Veronica или проблемах с сетью запрос падает по таймауту или по исключению. В логах:  
  `Ошибка делегирования Veronica (делегирование не сработало): ...`  
- Увеличить таймаут: `DELEGATE_VERONICA_TIMEOUT=120` (секунды).

### 5. Делегирование «неудачное»: ответ приходит, но с ошибкой (Ollama HTTP 404)

**Ситуация:** Victoria вызывает Veronica, Veronica отвечает HTTP 200 и `status: "success"`, но в `output` пользователь видит **«Сбой агента: Ollama HTTP 404»** (или похожее).

**Причина:** Делегирование по HTTP **сработало**. Неудача происходит **внутри Veronica**:

1. Veronica получает задачу и вызывает свой **OllamaExecutor** (планировщик и исполнитель).
2. Executor шлёт запрос в **Ollama** (`OLLAMA_BASE_URL`, в Docker обычно `http://host.docker.internal:11434`).
3. **НОВОЕ: Автовыбор модели** — если `VERONICA_MODEL` не задан, при первом запросе сканируются доступные модели Ollama и выбирается лучшая.
4. Если модель не найдена, Ollama возвращает **HTTP 404**.

**Итог:** Делегирование удачное (запрос дошёл до Veronica, ответ вернулся), но **результат неудачный** из‑за отсутствия модели в Ollama.

**Что сделать:**

- **Вариант А (рекомендуется).** Использовать **автовыбор модели** — просто не задавать `VERONICA_MODEL`, система сама выберет лучшую доступную:
  ```yaml
  # docker-compose.yml
  VERONICA_MODEL: ${VERONICA_MODEL:-}  # Пустое = автовыбор
  ```
  
- **Вариант Б.** Задать модель явно, которая **точно есть** в Ollama:
  ```bash
  # Проверить доступные модели
  curl http://localhost:11434/api/tags
  
  # В docker-compose для veronica-agent:
  VERONICA_MODEL: "qwen2.5-coder:32b"  # Или другая из списка
  ```

После этого перезапустить контейнер Veronica.

### 6. Veronica отвечает HTTP 500

- Victoria получает HTTP 500 и считает делегирование неудачным → fallback на Victoria.  
- Нужно, чтобы у Veronica был доступ к Ollama (правильный `OLLAMA_BASE_URL` и установленная модель). Иначе исправить окружение Veronica.

### 7. Тип задачи не «veronica»

- Делегирование вызывается только при `task_type == "veronica"`. Тип задаётся в `task_detector.py` по ключевым словам (например, «покажи файлы», «выполни», «сделай»).  
- Если фраза не попадает в `VERONICA_KEYWORDS` и эвристики кода, тип будет `enhanced` или `department_heads` — тогда вызывается Enhanced или agent.run, а не Veronica.

---

## Диагностика

1. **Логи Victoria:** при запросе смотреть:  
   - `[DELEGATION] VERONICA_URL=...`  
   - `Делегирую Veronica: <цель> -> <url>`  
   - либо `Veronica HTTP ... (делегирование не сработало)`  
   - либо `Ошибка делегирования Veronica ...`

2. **Статус задачи (async):** В ответе `GET /run/status/{task_id}` поле `stage` может быть `delegate_veronica` во время вызова Veronica; в `knowledge.execution_trace` при успешном делегировании: `routed_to: "veronica"`, `delegated_to: "Veronica"`.

3. **Проверка доступности Veronica из Victoria:**  
   - В контейнере Victoria:  
     `curl -s http://veronica-agent:8000/health`  
   - С хоста:  
     `curl -s http://localhost:8011/health`

---

## Файлы

| Что | Где |
|-----|-----|
| Детектор типа задачи | `src/agents/bridge/task_detector.py` |
| Вызов Veronica по HTTP | `src/agents/bridge/enhanced_router.py` (`delegate_to_veronica`) |
| Синхронный run | `src/agents/bridge/victoria_server.py` — `run_task` (блок `task_type == "veronica"`) |
| Фоновый run (async) | `src/agents/bridge/victoria_server.py` — `_run_task_background` (блок делегирования) |
| API Veronica | `src/agents/bridge/server.py` — `POST /run` |
