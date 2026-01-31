# Проверка логики: чат → Victoria → оркестратор → Veronica/сотрудники → результат

## Задуманный поток (от задания до ответа в чате)

1. **Пользователь** пишет в чат → Frontend отправляет сообщение → Backend `POST /api/chat/stream` → **Victoria** `POST /run` (goal).
2. **Victoria** при `/run`:
   - понимает цель: `_understand_goal_with_clarification(goal)` → при неоднозначности может вернуть **уточняющие вопросы** (status `needs_clarification`);
   - вызывает **оркестратор**: `IntegrationBridge.process_task(restated_goal)` → план, стратегия, **assignments** (кто какую подзадачу ведёт);
   - строит контекст: `_build_orchestration_context(bridge_result)` → текст плана/назначений;
   - **маршрутизация**:
     - если оркестратор назначил Veronica или `task_type == "veronica"` → **delegate_to_veronica** → результат от Вероники;
     - иначе при `use_enhanced` → **Victoria Enhanced** `solve()` с планом оркестратора в контексте → результат (в т.ч. делегирование сотрудникам через Enhanced);
     - иначе **agent.run()** (Victoria с инструментами) с целью, дополненной планом оркестратора.
3. **Результат** (текст ответа или ошибка) Victoria возвращает в теле ответа `/run` → Backend стримит его в SSE как `chunk` → Frontend показывает в чате.

---

## Что проверено и работает

| Этап | Где | Статус |
|------|-----|--------|
| Чат → Backend → Victoria `/run` | backend/app/routers/chat.py, backend/app/services/victoria.py | ✅ Backend вызывает `victoria.run(prompt, expert_name, project_context)`. |
| Понимание цели + уточняющие вопросы | victoria_server.py `_understand_goal_with_clarification`, при `needs_clarification` возвращается JSONResponse 200 с `clarification_questions` | ✅ Реализовано в Victoria. |
| Вызов оркестратора | victoria_server.py `run_task`: IntegrationBridge.process_task(restated_goal) → bridge_result | ✅ План и assignments сохраняются в `orchestration_plan`. |
| Контекст плана для LLM | `_build_orchestration_context(orchestration_plan)` → строка, подмешивается в цель для Enhanced и agent.run() | ✅ `orchestration_context_str` передаётся в enhanced.solve() и в agent.run(goal_for_run). |
| Предпочтение Veronica по назначению | `_orchestrator_recommends_veronica(orchestration_plan)` + task_type == "veronica" | ✅ При `prefer_veronica` вызывается `delegate_to_veronica()`, результат возвращается пользователю. |
| Enhanced с планом оркестратора | goal_for_enhanced = orchestration_context_str + "\n\nЗАДАЧА: " + goal | ✅ Контекст и история передаются в enhanced.solve(). |
| agent.run() с планом | goal_for_run = orchestration_context_str + "\n\nЗАДАЧА: " + goal_for_run | ✅ LLM получает план оркестратора и следует ему. |
| Результат в чат | Victoria возвращает output → backend берёт result/response/output → стримит chunk'ами | ✅ Итоговый текст отображается в чате. |

---

## Пробелы (что не доведено до чата)

### 1. Уточняющие вопросы — доведено до чата

- **Victoria** при `needs_clarification` возвращает 200 и JSON: `{ "status": "needs_clarification", "clarification_questions": [...] }`.
- **Backend** (после правок): после `victoria.run()` проверяет `result.get("status") == "needs_clarification"`; если да — шлёт шаг `stepType: "clarification"` с текстом вопросов и стримит текст «Нужно уточнение: • вопрос1 • вопрос2…» chunk'ами, затем `end`. Во фронте шаг типа clarification уже отображается (иконка ❓).
- **Victoria client** возвращает `clarification_questions` в ответе, чтобы backend мог их отдать в чат.

### 2. История чата не передаётся в Victoria из Web IDE

- **Victoria** `/run` принимает тело с полем `chat_history` (список пар user/assistant) и использует его в Enhanced и контексте.
- **Backend** в chat router в `victoria.run()` **не передаёт** `chat_history` (только prompt, expert_name, project_context).
- В результате Victoria при ответе в Web IDE не видит предыдущих сообщений диалога.

**Рекомендация:** в backend при вызове Victoria передавать историю чата (например, последние N пар сообщений из store или из запроса) в теле `/run` как `chat_history`, если Victoria API это поддерживает.

---

## Краткая схема (как есть)

```
Чат (Frontend)
    → POST /api/chat/stream (content, expert_name, mode)
Backend
    → POST Victoria /run (goal=content, expert_name, project_context)  [без chat_history]
Victoria /run
    → _understand_goal_with_clarification  [при needs_clarification — backend стримит step clarification + текст вопросов в чат]
    → IntegrationBridge.process_task(goal)  → orchestration_plan (план, assignments)
    → _build_orchestration_context(plan)
    → prefer_veronica? → delegate_to_veronica → output
    → иначе use_enhanced? → enhanced.solve(goal + plan, context) → output
    → иначе agent.run(goal + plan) → output
    → return TaskResponse(output=...)
Backend
    → стримит output как chunk'и → Frontend
Чат
    → отображает ответ; при needs_clarification — шаг «Уточняющие вопросы» и список вопросов (stepType clarification + chunk'и).
```

---

## Итог

- **Цепочка от задания до выполнения и до ответа в чате реализована:** оркестратор вызывается, план и назначения передаются в Victoria, предпочтение Veronica по назначению работает, результат возвращается и стримится в чат.
- **Уточняющие вопросы доведены до чата:** при ответе Victoria `needs_clarification` backend отправляет шаг типа clarification и текст вопросов в SSE; во фронте они отображаются (иконка ❓). Пользователь может ответить следующим сообщением.
- **История чата из Web IDE в Victoria не передаётся** — при необходимости её нужно добавить в вызов `/run` со стороны backend (и поддержку в Victoria API).
