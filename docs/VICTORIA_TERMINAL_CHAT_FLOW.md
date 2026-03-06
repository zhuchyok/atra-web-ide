# Чат с Victoria через терминал: через какую модель и как обрабатывается

**Кратко:** Терминал шлёт запрос на Victoria (8010). Обработка идёт по разным путям; модель зависит от пути (Fast Path → MLX/Ollama; полный путь → planner + executor в Ollama или Victoria Enhanced → ai_core → та же модель).

---

## Этап 1: Терминал → Victoria

- **Скрипт:** `scripts/victoria_chat_standalone.py` (или `bash scripts/chat_victoria.sh`).
- **Запрос:** `POST http://localhost:8010/run` (или `VICTORIA_REMOTE_URL`).
- **Тело:** `goal`, `project_context`, `session_id`, `chat_history`, `max_steps`.
- **Ответ:** JSON (синхронно, без стриминга). Обработка целиком на стороне Victoria.

---

## Этап 2: Сервер Victoria (POST /run) — вход

- Принимается `body.goal`, `body.project_context`, `body.session_id`, `body.chat_history`, `body.max_steps`.
- Выставляется `MAIN_PROJECT` и контекст проекта для RAG/промптов.
- Решается, **быстрый ли запрос** (приветствие, «что умеешь», короткая фраза) или нужен полный цикл.

---

## Этап 3: Fast Path (простые сообщения)

**Когда срабатывает:** приветствия («привет», «здравствуй»), «что ты умеешь», короткие простые фразы (без `use_enhanced`) или VIP-слова (стратег, CEO и т.д.).

**Модель:**

- Выбор модели: `_select_model_for_chat(goal)`:
  - стратегия/код/длинный текст → **victoria-wisdom-v3.5**;
  - короткий текст (< 200 символов) → **tinyllama:1.1b-chat** (быстрая);
  - по умолчанию → **victoria-wisdom-v3.5**.
- Генерация: **`_generate_via_mlx_or_ollama(goal, ideal_model)`**:
  1. Сначала пробуется **MLX** (порт 11435, `/api/chat`), если задан `agent.executor.mlx_url`;
  2. Если MLX не ответил — **Ollama** (порт 11434) через `agent.executor.ask(..., model=ideal_model)`.

**Итог:** ответ сразу 200, без стратегии и без полного цикла. Модель — одна из: MLX (victoria-wisdom-v3.5 или tinyllama) или Ollama (то же имя модели).

---

## Этап 4: Полный путь (не Fast Path) — стратегия и понимание цели

- **Стратегия:** `_select_strategy(agent, goal, session_summary)` — один вызов **planner** (Ollama). Модель planner: **VICTORIA_PLANNER_MODEL** или, если не задана, **VICTORIA_MODEL** (часто victoria-wisdom-v3.5).
- При стратегиях `need_clarification` или `decline_or_redirect` — ответ сразу, без выполнения задачи.
- **Понимание цели:** `_understand_goal_with_clarification(agent, goal)` — снова вызов **planner** (Ollama), та же модель.

---

## Этап 5: Полный путь — выполнение (кто отвечает)

Возможны три варианта:

**Вариант A — Veronica (порт 8011)**  
Если тип задачи «veronica» и Enhanced включён: запрос уходит в Veronica. Модель на стороне Veronica (локальная модель по её конфигу).

**Вариант B — Victoria Enhanced (knowledge_os)**  
Если включён `use_enhanced` и не пошли в Veronica: вызывается **VictoriaEnhanced.solve()** → внутри **ai_core.run_smart_agent_async()** (Knowledge OS).  
Там используются:

- кэш (семантический), или
- локальные модели через **LocalAIRouter** (Ollama/MLX): выбор по категории задачи (coding, reasoning и т.д.), часто **victoria-wisdom-v3.5** или модель из сканера доступных моделей.

**Вариант C — agent.run() (Victoria Agent)**  
Если не Enhanced или после неудачи Veronica: выполнение через **VictoriaAgent.run()** (ReAct-цикл с инструментами).  
Модели:

- **Planner (план):** Ollama, **VICTORIA_PLANNER_MODEL** (или VICTORIA_MODEL).
- **Executor (шаги):** Ollama, **VICTORIA_MODEL** (или лучшая доступная при первом запуске).

Итог полного пути: ответ формирует либо Veronica, либо Victoria Enhanced (Ollama/MLX через ai_core), либо Victoria Agent (Ollama planner + executor).

---

## Этап 6: Откуда берутся имена моделей

- **VICTORIA_MODEL** — явная модель для executor (и по умолчанию для planner). Пример: `victoria-wisdom-v3.5:latest`.
- **VICTORIA_PLANNER_MODEL** — модель для стратегии и понимания цели. Если не задана — совпадает с VICTORIA_MODEL.
- В Fast Path и в Enhanced дополнительно используется **сканер доступных моделей** (Ollama/MLX): при отсутствии явной настройки подставляется «лучшая» доступная (например, 104b → 70b → 32b → …).

---

## Сводная таблица (через какую модель идёт обработка)

| Этап / путь               | Где считается        | Модель (по умолчанию)                            |
| ------------------------- | -------------------- | ------------------------------------------------ |
| Fast Path (привет и т.п.) | Victoria 8010        | MLX или Ollama: victoria-wisdom-v3.5 / tinyllama |
| Стратегия + understand    | Victoria 8010        | Ollama: VICTORIA_PLANNER_MODEL / VICTORIA_MODEL  |
| Veronica                  | Veronica 8011        | Локальная модель Veronica                        |
| Victoria Enhanced         | knowledge_os ai_core | Ollama/MLX (LocalAIRouter, часто v3.5)           |
| Victoria Agent.run()      | Victoria 8010        | Ollama: planner + executor (VICTORIA\_\*)        |

---

## Как проверить свою конфигурацию

- Логи при старте Victoria: `[VICTORIA_INIT] Planner model: ... Executor model: ...`
- В запросе: `[REQUEST] Current executor model: ... Current planner model: ...`
- В .env: `VICTORIA_MODEL`, `VICTORIA_PLANNER_MODEL` (и при необходимости MLX_URL для Fast Path).

_Документ создан по коду: victoria_server.py, victoria_chat_standalone.py, ai_core, LocalAIRouter._
