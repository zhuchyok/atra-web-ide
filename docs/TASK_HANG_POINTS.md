# Где может зависнуть задача Victoria

Документ описывает **точки возможного зависания** в цепочке от `POST /run` до ответа и как по логам/статусу понять, на каком этапе застряла задача.

---

## Цепочка выполнения (кратко)

1. **Приём запроса** — `run_task` / `_run_task_background`
2. **Understand** — `_understand_goal_with_clarification` → `agent.understand_goal(goal)` → **planner.ask()** (1 вызов LLM)
3. **Маршрутизация** — `detect_task_type`, `should_use_enhanced`
4. **Делегирование Veronica** (если `task_type == "veronica"`) — `delegate_to_veronica()` → HTTP POST на :8011
5. **Victoria Enhanced** (если не veronica или fallback) — `enhanced.solve()` → Department Heads / TaskDelegator / react/simple
6. **Стандартный режим** — `agent.run(goal, max_steps)` → цикл: understand_goal → plan (опционально) → шаги step() до finish или max_steps

---

## Точки зависания и таймауты

| Этап | Где код | Таймаут | Что может держать |
|------|---------|---------|--------------------|
| **Understand** | `_understand_goal_with_clarification` → `agent.understand_goal` → planner.ask | **180 с** (OllamaExecutor) | Медленный Ollama/модель; долгий ответ LLM. |
| **Уточняющие вопросы** | `_generate_clarification_questions` → planner.ask | **180 с** | То же. |
| **Делегирование Veronica** | `delegate_to_veronica` → aiohttp POST :8011 | **60 с** (`DELEGATE_VERONICA_TIMEOUT`) | Veronica не отвечает, сеть, перегрузка :8011. |
| **Victoria Enhanced** | `enhanced.solve()` | **Нет общего таймаута** | Department Heads (БД + несколько LLM), делегирование (до 300 с в multi_agent_collaboration), затем react/simple — много шагов. |
| **agent.run()** | `VictoriaAgent.run` → цикл step() | **Нет общего таймаута** | До **max_steps** (по умолчанию 500, env VICTORIA_MAX_STEPS) шагов; каждый шаг — один вызов LLM. |
| **Один шаг агента** | `step()` → local_router.run_local_llm или executor.ask | **120 с** (LocalAIRouter) / **180 с** (OllamaExecutor) | Медленная модель, долгая генерация. |
| **План** | `agent.plan(restated)` → planner.ask | **180 с** | То же. |

Итог: задача может «висеть» долго, если:
- долго отвечает **Ollama** (understand, plan, каждый step);
- **Veronica** не отвечает в течение 60 с (потом fallback на Victoria);
- **Victoria Enhanced** уходит в Department Heads или в многошаговый react без ограничения по времени;
- **agent.run()** делает много шагов (до 80) без общего таймаута.

---

## Как выяснить, где зависло

### 1. Логи с префиксом `[TRACE]`

В коде добавлены логи вида:

- `[TRACE] _run_task_background: start`
- `[TRACE] _run_task_background: before understand_goal`
- `[TRACE] _run_task_background: after understand_goal`
- `[TRACE] _run_task_background: before enhanced.solve`
- `[TRACE] _run_task_background: after enhanced.solve`
- `[TRACE] _run_task_background: before agent.run`
- `[TRACE] _run_task_background: after agent.run`
- В `agent.run`: `[TRACE] run: start`, `[TRACE] run: after understand_goal`, `[TRACE] run: after plan`, `[TRACE] run: step N`

**Последняя строка с `[TRACE]` в логах** — этап, на котором задача сейчас держится (или зависла).

### 2. Поле `stage` в статусе задачи (async_mode)

При опросе `GET /run/status/{task_id}` в ответ добавлено поле **`stage`** (если есть):

- `understand_goal` — ждём понимания цели;
- `delegate_veronica` — ждём ответа Veronica;
- `enhanced_solve` — внутри Victoria Enhanced;
- `agent_run` — выполняем agent.run();
- `agent_run_step` — внутри цикла шагов (можно с номером шага при доработке).

Если задача «висит», смотрите последний залогированный и выданный в `stage` этап — это и есть место зависания.

### 3. Переменные окружения

- **DELEGATE_VERONICA_TIMEOUT** — таймаут делегирования Veronica (по умолчанию 60 с).
- **VICTORIA_MAX_STEPS** — максимум шагов в agent.run (по умолчанию 500; в docker-compose задано 500). Уменьшение сокращает худший случай по времени.

---

## Рекомендации

1. **Общий таймаут на задачу** — обернуть выполнение в `asyncio.wait_for(..., timeout=600)` и при срабатывании логировать этап (stage) и возвращать пользователю «Task timed out at stage X».
2. **Ограничить max_steps** — например 20–30 для обычных запросов, чтобы избежать очень долгого цикла.
3. **Мониторинг** — по логам `[TRACE]` и полю `stage` в статусе строить дашборд «на каком этапе сколько задач проводят время».

Файлы с трассировкой:
- `src/agents/bridge/victoria_server.py` — `_run_task_background`, `run_task`, обновление `store["stage"]`, логи `[TRACE]`.
- `src/agents/core/base_agent.py` — в цикле `run()` логи `[TRACE] run: step N` (опционально).
- `src/agents/bridge/victoria_server.py` — `get_run_status` возвращает `stage`.
