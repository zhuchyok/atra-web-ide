# Диагностика внедрённых решений

**Дата:** 2026-01-30  
**Действия:** перезапуск бэкенда (`docker-compose restart backend`), пересборка (`docker-compose up -d --build backend`).

---

## 1. Что перезапущено

- **Backend (atra-web-ide-backend):** пересобран образ и перезапущен контейнер. Порт 8080.
- После пересборки в контейнере актуальный код: шаги агента с flush, режимы agent/plan/ask, обработка needs_clarification, эндпоинт /plan.

---

## 2. Чеклист внедрённых решений и как проверить

### 2.1 Backend

| Решение                                      | Где                                  | Проверка                                                                                                                                                                |
| -------------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Health**                                   | `GET /health`, `GET /api/health`     | `curl -s http://localhost:8080/health` → `{"status":"healthy",...}`                                                                                                     |
| **Chat status**                              | `GET /api/chat/status`               | `curl -s http://localhost:8080/api/chat/status` → Victoria, MLX/Ollama                                                                                                  |
| **SSE stream с шагами**                      | `POST /api/chat/stream`              | В ответе до chunk'ов должны быть строки `"type": "step"` (Анализ запроса, Запрос к Victoria Agent и т.д.). После каждого step — SSE-комментарий `: ` для сброса буфера. |
| **Режимы agent / plan / ask**                | body `mode` в `/api/chat/stream`     | `mode: "plan"` → один step «Составляю план» + план текстом; `mode: "ask"` → быстрый ответ через MLX; `mode: "agent"` (по умолчанию) → полный Victoria с шагами.         |
| **Эндпоинт «только план»**                   | `POST /api/chat/plan`                | `curl -X POST http://localhost:8080/api/chat/plan -H "Content-Type: application/json" -d '{"goal":"план теста"}'` → JSON с полем `plan`.                                |
| **Уточняющие вопросы (needs_clarification)** | В sse_generator после victoria.run() | Если Victoria вернула `status: "needs_clarification"`, backend шлёт step `stepType: "clarification"` и текст вопросов chunk'ами.                                        |
| **Victoria client: clarification_questions** | backend/app/services/victoria.py     | В ответе run() есть поле `clarification_questions` при needs_clarification.                                                                                             |

### 2.2 Frontend

| Решение                                          | Где                            | Проверка                                                                                   |
| ------------------------------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------ |
| **Вкладки Чат / Агент / План**                   | App.svelte                     | В центре три вкладки: Чат, Агент, План; по умолчанию Чат.                                  |
| **Режимы Agent / Plan / Ask в чате**             | Chat.svelte, chat.js           | Над полем ввода переключатель ∞ Агент \| 📋 План \| 💬 Ask; в API уходит `mode`.           |
| **Панель «Шаги агента» при стриминге**           | Chat.svelte                    | Во время стриминга над сообщениями блок с шагами (💭 🔍 ⚡) с анимацией появления.         |
| **Шаги в сообщении (вертикальная линия, точки)** | Chat.svelte                    | В каждом ответе ассистента над текстом — шаги в стиле Cursor (линия слева, точки по типу). |
| **Мигающий курсор при стриминге**                | Chat.svelte                    | Только у последнего (стримящегося) сообщения в конце текста.                               |
| **Точки «думает» / «Агент работает»**            | Chat.svelte                    | Анимация трёх точек в заголовке панели шагов и в блоке «Агент работает…».                  |
| **Парсинг SSE: комментарии**                     | chat.js                        | Строки, начинающиеся с `:`, пропускаются (flush).                                          |
| **План-панель**                                  | PlanPanel.svelte, вкладка План | Поле «Задача», кнопка «Получить план», вывод текста плана.                                 |

### 2.3 Цепочка Victoria → оркестратор → Veronica / сотрудники

| Решение                                 | Где                                                 | Проверка                                                                 |
| --------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------ |
| **Оркестратор вызывается**              | victoria_server.py run_task                         | IntegrationBridge.process_task(goal) → orchestration_plan.               |
| **План передаётся в LLM**               | \_build_orchestration_context, goal_for_run         | Цель для agent.run() и enhanced.solve() дополняется планом оркестратора. |
| **Предпочтение Veronica по назначению** | \_orchestrator_recommends_veronica, prefer_veronica | При назначении оркестратором Veronica вызывается delegate_to_veronica(). |
| **Результат в чат**                     | Backend стримит output Victoria                     | Итоговый текст отображается в чате.                                      |

---

## 3. Команды для ручной диагностики (когда бэкенд доступен)

```bash
# 1. Health
curl -s http://localhost:8080/health

# 2. Chat status (Victoria, MLX/Ollama)
curl -s http://localhost:8080/api/chat/status

# 3. Наличие step в SSE (первые 5 сек ответа)
curl -s -N -m 5 -X POST http://localhost:8080/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"content":"тест","expert_name":"Виктория","use_victoria":true,"mode":"agent"}' | head -c 4000

# 4. Эндпоинт плана (может быть долгим — Victoria /plan)
curl -s -m 60 -X POST http://localhost:8080/api/chat/plan \
  -H "Content-Type: application/json" \
  -d '{"goal":"составь план теста"}'

# 5. Скрипт проверки шагов
./scripts/verify_chat_steps.sh
# или с другим хостом:
./scripts/verify_chat_steps.sh http://localhost:8080
```

---

## 4. Результаты проверки (2026-01-30)

- **Исправлена ошибка:** в `chat.py` была SyntaxError (f-string с backslash в expression) — исправлено: контент шага «Эксперт найден» вынесен в переменную `exploration_content`.
- **Backend перезапущен и пересобран** — контейнер atra-web-ide-backend пересобран и запущен без ошибок.

| Проверка                               | Результат                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **GET /health**                        | 200, `{"status":"healthy","dependencies":{"victoria":"ok","ollama":"healthy"}}`                                                                                                                                                                                                                                                                                                                                                             |
| **GET /api/chat/status**               | 200, Victoria ok, MLX unavailable (нормально, если MLX не запущен)                                                                                                                                                                                                                                                                                                                                                                          |
| **POST /api/chat/stream** (mode=agent) | В ответе есть события `"type": "step"`: thought «Анализ запроса», exploration «Эксперт найден», action «Запрос к Victoria Agent»; между ними SSE-комментарии `: ` (flush). Скрипт `./scripts/verify_chat_steps.sh` — **OK**.                                                                                                                                                                                                                |
| **POST /api/chat/plan**                | Backend вызывает Victoria `POST /plan`; если Victoria (контейнер victoria-agent) возвращает 404 — у контейнера Victoria может быть старая сборка без маршрута `/plan`. В коде Victoria (`victoria_server.py`) маршрут `@app.post("/plan")` есть; пересобрать образ Victoria: `docker-compose -f knowledge_os/docker-compose.yml build victoria-agent --no-cache && docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent`. |

---

## 5. Если бэкенд не отвечает на localhost:8080

- **Docker:** проверить, что контейнер запущен: `docker ps | grep backend`. Логи: `docker logs atra-web-ide-backend`.
- **Сеть:** при запуске только backend без фронта запросы с хоста на localhost:8080 должны работать (порт 8080:8000 проброшен). Если используется другой хост/порт — подставить в команды выше.
- **Локальный запуск (без Docker):** из корня проекта: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8080`. Тогда проверки — те же curl на http://localhost:8080.

---

## 6. Краткий итог

| Категория                                                    | Статус                                                                            |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Перезапуск/пересборка бэкенда                                | Выполнено                                                                         |
| Health, chat status                                          | Реализовано, при доступности бэкенда проверяется curl'ом                          |
| SSE шаги (step), flush                                       | Реализовано в коде; проверка: чат в браузере или curl с таймаутом 5+ сек          |
| Режимы agent/plan/ask                                        | Реализовано в backend и frontend                                                  |
| Эндпоинт /api/chat/plan                                      | Реализован в backend                                                              |
| Уточняющие вопросы (needs_clarification)                     | Обработка в backend, отображение шага clarification во фронте                     |
| Цепочка оркестратор → Victoria → Veronica/Enhanced/agent.run | Реализована в Victoria, описана в CHAT_VICTORIA_ORCHESTRATOR_FLOW_VERIFICATION.md |
| Вкладки и панель шагов в стиле Cursor                        | Реализованы во фронте                                                             |

Полная проверка в реальном времени: открыть http://localhost:3000 (или порт фронта), вкладка «Агент», режим «∞ Агент», отправить сообщение — должны по очереди появиться шаги, затем ответ.
