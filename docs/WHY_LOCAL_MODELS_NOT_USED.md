# Почему не использовались локальные модели (Ollama / MLX)?

**Отчёт от Виктории (Team Lead)**  
**Дата:** 2026-01-28

---

## 1. Кто чем занимается

### Оркестратор
- **enhanced_orchestrator.py** — запускает циклы оркестрации, создаёт задачи, назначает экспертов.
- При необходимости «мозга» вызывает **run_smart_agent_async** (ai_core) с `expert_name="Виктория"`, `category="orchestrator"`.
- То есть оркестратор сам не решает «Ollama или MLX» — это делает **ai_core** и **LocalAIRouter**.

### Виктория (я)
- В коде «Виктория» — это **роль** в промпте и логике роутинга, а не отдельный процесс.
- **Планирование (ТЗ):** генерируется через **\_run_cloud_agent_async(spec_prompt)**. Внутри него **сначала** вызывается **LocalAIRouter.run_local_llm** (Ollama/MLX), и только при неудаче — cursor-agent.
- **Аудит кода:** то же самое — **\_run_cloud_agent_async(audit_prompt)** → снова сначала локальные модели, потом облако.
- **Исполнение (код по ТЗ):** явно делается через **router.run_local_llm(worker_prompt, category="coding")** — только локальные модели (MLX/Ollama).

То есть по задумке и я (планирование/аудит), и «воркер» (исполнение) должны использовать локальные модели, если они доступны.

### Вероника
- **VeronicaWebResearcher** — включается, когда в запросе есть признаки веб-поиска (новости, тренды, 2025, «актуальные» и т.д.).
- Она вызывает **свои** модели (в `veronica_web_researcher.py` — research/coding/fast), там указаны MLX/Ollama по URL. Если дашборд/worker не та задача, что с веб-поиском, Вероника в цепочке вообще не участвует.

### Вся команда (worker + ai_core)
- **smart_worker_autonomous** забирает задачи из БД и для каждой (кроме разведки и т.п.) вызывает **run_smart_agent_async(prompt, expert_name, …)**.
- Дальше решение «локально или облако» принимает **ai_core** по правилам ниже. Локальные модели — через **LocalAIRouter** (Ollama 11434, MLX 11435).

---

## 2. Когда и как выбираются локальные модели

### В ai_core.run_smart_agent_async

1. **Кодинг-задачи** (ключевые слова: код, программируй, рефакторинг, тест, аудит и т.д.):
   - Планирование (ТЗ) → **\_run_cloud_agent_async** → внутри **сначала** LocalAIRouter.run_local_llm, потом cursor-agent.
   - Исполнение (по ТЗ) → **только** router.run_local_llm(..., category="coding").
   - Аудит → снова **\_run_cloud_agent_async** → снова сначала локальные модели.

2. **Остальные задачи:**
   - Вход в «локальный/параллельный» путь:  
     `if router and (images or router.should_use_local(prompt, category)) or needs_web_search`
   - **should_use_local** возвращает True, если:
     - включён USE_LOCAL_LLM (по умолчанию true),
     - или есть images,
     - или category в LOCAL_TASK_CATEGORIES / MODEL_MAP,
     - или в промпте есть фразы типа «анализ логов», «проверь код», «суммаризируй» и т.д.,
     - или промпт длинный (>2000 символов) без «архитектура»/«стратегия».
   - Если условие **не** выполняется — запрос идёт по «облачному» пути: сбор контекста, сжатие, затем **\_run_cloud_agent_async**. Но и там внутри **сначала** вызывается LocalAIRouter.run_local_llm, и только при неудаче — cursor-agent.

### Итог по коду
- По архитектуре **локальные модели (Ollama/MLX) должны использоваться первыми** везде, где есть router и они доступны.
- Если в твоей задаче они не использовались, значит либо запрос не дошёл до run_local_llm, либо **run_local_llm завершился ошибкой/таймаутом** и сработал fallback на cursor-agent.

---

## 3. Почему локальные модели могли не использоваться (причины)

1. **Worker в Docker, Ollama/MLX на хосте**
   - Router использует `host.docker.internal:11434` (Ollama) и `host.docker.internal:11435` (MLX).
   - Если worker крутится в контейнере на машине, где **нет** Ollama/MLX (или они не проброшены), запросы к ним падают по таймауту/connection refused → fallback на cursor-agent.

2. **Circuit breaker «local_models»**
   - После нескольких неудачных вызовов локальных моделей breaker открывается и локальный путь временно не вызывается → идём в облако.

3. **disaster_recovery.can_use_local_models() == False**
   - Система считает локальные модели недоступными и явно не вызывает их.

4. **USE_LOCAL_LLM=false**
   - В окружении worker’а переменная выключена → should_use_local всегда False → локальный маршрут не выбирается (хотя _run_cloud_agent_async всё равно пробует локальный router первым, если он есть).

5. **Таймауты**
   - run_local_llm или health-check к узлам долго отвечают → таймаут → считается «недоступно» → fallback.

6. **Специальные типы задач**
   - **Разведка (scout):** обрабатывается **scout_task_processor** → **EnhancedScoutResearcher**. Виктория/Вероника/оркестратор в этой цепочке не вызываются; внутри разведки свой вызов MLX/Ollama только в **deep_analysis_with_llm**. Если там падало — могли видеть «модель N/A» или пустые результаты.
   - Остальные задачи идут через run_smart_agent_async и должны проходить через LocalAIRouter при доступности.

---

## 4. Что сделать, чтобы локальные модели использовались

1. **Проверить доступность Ollama/MLX из контейнера worker:**
   - Из контейнера: `curl -s http://host.docker.internal:11434/api/tags` и `curl -s http://host.docker.internal:11435/health` (или ваши реальные хосты).
   - Если worker не на том же хосте, что Mac с Ollama/MLX — задать правильные URL через переменные (например OLLAMA_BASE_URL, MLX_API_URL).

2. **Включить и проверить USE_LOCAL_LLM:**
   - В окружении worker: `USE_LOCAL_LLM=true` (по умолчанию так и есть в коде).

3. **Смотреть логи worker и ai_core:**
   - Сообщения вида: `[LOCAL ROUTE]`, `[FALLBACK] Used local model`, `[WORKER START] Executing TS locally`, `[ML ROUTER]` / `[HEURISTIC ROUTER]` — значит пошло в локальные модели.
   - Сообщения вида: `[CLOUD TIMEOUT]`, `[FALLBACK] Local router failed`, `cursor-agent not found`, `Circuit breaker open` — значит локальные модели не сработали и использовалось облако.

4. **Расширить should_use_local (по желанию):**
   - Добавить категории в LOCAL_TASK_CATEGORIES или более широкие эвристики по промпту, чтобы больше задач шло в «локальный» ветку до вызова _run_cloud_agent_async.

---

## 5. Что изменено в коде (продолжение)

1. **Приоритет локальных моделей в _run_cloud_agent_async (ai_core.py)**  
   В комментариях и логах явно указано: сначала локальные модели (Ollama/MLX), затем cursor-agent. Лог: `[LOCAL FIRST] Использована локальная модель` или `[LOCAL FIRST] Локальный роутер недоступен`.

2. **should_use_local (local_router.py)**  
   - Добавлены категории `autonomous_worker`, `orchestrator`, `general`, `research`, `reasoning`, `coding`, `fast` — для них всегда предпочитаем локальный маршрут.  
   - Для любой заданной категории (category is not None) по умолчанию возвращаем True, чтобы больше задач шло в локальный путь.  
   - Добавлено логирование, когда локальный маршрут отключён из‑за USE_LOCAL_LLM.

3. **Логирование выбора маршрута (ai_core.py)**  
   При входе в run_smart_agent_async пишется:  
   - `[ROUTE] Выбран локальный маршрут (Ollama/MLX)` — задача пойдёт в router.run_local_llm / параллельный путь.  
   - `[ROUTE] Выбран облачный маршрут` — задача пойдёт в «Full Cloud Call», но внутри _run_cloud_agent_async снова сначала вызываются локальные модели.

По логам worker/ai_core теперь можно увидеть, какой маршрут был выбран и использовались ли Ollama/MLX.
