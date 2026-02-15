# Промпты Victoria — версионирование и владельцы

Документ фиксирует, **где какой промпт** живёт, **откуда читается** и **кто владелец** (план «как я» п.11.3).

## Таблица промптов

| Компонент | Файл / конфиг | Назначение | Владелец |
|-----------|----------------|------------|----------|
| **Simple-промпт** | `configs/victoria_common.py` → `build_simple_prompt()` | Единый шаблон для быстрых ответов (эталон, RAG, runbook, похожие задачи). Используется в `victoria_enhanced` при методе `simple`. | Team Lead / Backend |
| **Русский + краткость** | `configs/victoria_common.py` → `PROMPT_RUSSIAN_ONLY`, `PROMPT_RUSSIAN_AND_BREVITY_LINES` | Фрагменты «только русский», «кратко 3–5 предложений» для куратора и эталонов. | Team Lead |
| **Мировые практики** | `configs/victoria_common.py` → `WORLD_PRACTICES_LINE` | Один источник истины, библия (MASTER_REFERENCE). Подставляется в simple. | Team Lead |
| **Возможности Victoria** | `configs/victoria_capabilities.txt` → `get_capabilities_text()` | Текст «что ты умеешь» / «кто ты». Env: `VICTORIA_CAPABILITIES_FILE`. | Team Lead |
| **Логика корпорации** | `configs/corporation_thinking.txt` → `get_thinking_context()` | Блок «КАК МЫ МЫСЛИМ» в промпте Victoria. Env: `CORPORATION_THINKING_FILE`. Источник идей: docs/THINKING_AND_APPROACH.md. | Team Lead |
| **ReAct: think** | `knowledge_os/app/react_agent.py` → `_build_think_prompt()` | Промпт фазы «подумай»: цель, контекст, история шагов. Использует `PROMPT_RUSSIAN_ONLY`. | Backend / Victoria Enhanced |
| **ReAct: act** | `knowledge_os/app/react_agent.py` → `_build_act_prompt()` | Промпт фазы «действуй»: мысль, доступные инструменты. | Backend / Victoria Enhanced |
| **ReAct: reflect** | `knowledge_os/app/react_agent.py` → `_build_reflect_prompt()` | Промпт фазы «рефлексия»: цель, шаги, итог. | Backend / Victoria Enhanced |
| **План (Victoria)** | `src/agents/bridge/victoria_server.py` | `plan_prompt` для фазы plan (understand_goal, plan). Формируется в коде с экспертами и контекстом. | Backend |
| **План (Veronica)** | `src/agents/bridge/server.py` (Veronica) | Промпт «Составь СТРОГИЙ пошаговый план» для планировщика Veronica. | Backend |
| **Project prompt** | `src/agents/bridge/victoria_server.py` | Базовый контекст запроса: возможности, «КАК МЫ МЫСЛИМ», project_context. Собирается при каждом запросе. | Backend |
| **Strategy selection** | `src/agents/bridge/victoria_server.py` → `_select_strategy()` | Один вызов planner в начале цепочки: по цели определить strategy (quick_answer / deep_analysis / need_clarification / decline_or_redirect), reason, confidence. Вход: goal, опционально session summary. | Backend / Team Lead |
| **Reflection checkpoint** | `knowledge_os/app/recap_framework.py` → `_should_revise_plan()` | После провала/пустого шага ReCAP: один вызов LLM «пересмотреть план? ДА/НЕТ + причина». Вход: цель, план (кратко), шаг, результат. При «ДА» — пересборка плана с контекстом предыдущей попытки. | Backend |
| **Final confidence** | strategy в victoria_server + _inject_strategy_into_knowledge (Фаза 4) | confidence 0–1 из слоя стратегии; при confidence < 0.7 в knowledge добавляется uncertainty_reason (из planner или reason). Клиенты могут показывать предупреждение при низкой уверенности. | Backend |
| **Неопределённость в ответе** | `configs/victoria_common.py` → PROMPT_UNCERTAINTY_LINE, build_simple_prompt | В simple-промпт добавлен пункт 7: при недостатке данных явно писать «здесь я не уверен», «нужны данные», «рекомендую проверить». Не заменяет anti_hallucination. | Арина |

## Где что редактировать

- **Изменить текст «что умеешь»** → `configs/victoria_capabilities.txt` (или файл из `VICTORIA_CAPABILITIES_FILE`).
- **Изменить логику корпорации в промпте** → `configs/corporation_thinking.txt` (или `CORPORATION_THINKING_FILE`).
- **Изменить шаблон simple (структура, пункты)** → `configs/victoria_common.py` → `build_simple_prompt()`.
- **Изменить ReAct-фразы (think/act/reflect)** → `knowledge_os/app/react_agent.py` → `_build_*_prompt()`.
- **Изменить план Victoria (формулировки фаз)** → `src/agents/bridge/victoria_server.py` (поиск по `plan_prompt`, `understand_goal`).

## Связь с библией

- Общая архитектура и последние изменения: **docs/MASTER_REFERENCE.md**.
- Правки из чатов (capabilities, thinking, куратор): **docs/CHANGES_FROM_OTHER_CHATS.md**.
