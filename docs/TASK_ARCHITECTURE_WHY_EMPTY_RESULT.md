# Почему пользователь видит пустой результат (только «статус: finish»)

**Дата:** 2026-01-30  
**Симптом:** Запрос «Создай пуллинг бота с aiogram» → ответ «Задача выполнена экспертом Дмитрий (статус: finish)» без кода и без реального результата.

---

## Архитектура **работает** — цепочка выполняется

1. **Роутинг:** Victoria Enhanced получает цель → `_should_use_department_heads` → True (задача не casual chat).
2. **Отдел:** `department_heads_system.coordinate_department_task` → выбирается отдел (например, ML/AI) и эксперт (Дмитрий).
3. **Стратегия:** `strategy == "simple"` → один эксперт.
4. **Исполнение:** `_execute_department_task` → создаётся **ReActAgent** с system_prompt эксперта → вызывается `expert_agent.run(goal=goal, context=None)`.
5. **Ответ пользователю:** Берётся `result` из возврата `_execute_department_task` и отдаётся в чат.

То есть маршрут «задача → отдел → эксперт → ReActAgent» срабатывает.

---

## Где теряется результат

Проблема не в «архитектуре обработки задач», а в том, **что возвращает исполнитель** и **как это превращается в текст для пользователя**.

### 1. ReActAgent возвращает пустой «результат»

В `victoria_enhanced._execute_department_task` (порядок строк ~1216–1232):

```python
result_dict = await expert_agent.run(goal=goal, context=None)
result = result_dict.get("final_reflection", "")
if not result and result_dict.get("steps"):
    last_step = result_dict["steps"][-1]
    result = last_step.get("observation", "") or last_step.get("reflection", "")
if not result:
    result = f"Задача выполнена экспертом '{expert_name}' (статус: {result_dict.get('status', 'unknown')})"
```

То есть пользователю показывается:

- либо `final_reflection`,
- либо `observation` / `reflection` последнего шага,
- а если оба пустые — **подставная строка** «Задача выполнена экспертом 'Дмитрий' (статус: finish)».

У тебя как раз сработал этот fallback: модель вернула `status: finish`, но не заполнила ни `final_reflection`, ни последний `observation`/`reflection`.

### 2. Почему ReActAgent даёт пустой результат

В `react_agent.py` при действии `finish`:

```python
elif action == "finish":
    output = action_input.get("output", action_input.get("result", ""))
    return output
```

Итоговая «наблюдательность» (observation) для шага с `finish` — это только то, что модель положила в `input.output` или `input.result`. Если модель вызвала `finish` без `output`/`result` (или с пустой строкой), то:

- последний шаг даёт пустое `observation`;
- `final_reflection` тоже часто не заполняется полезным текстом;
- в итоге в чат уходит запасная фраза про «статус: finish».

Типичные причины:

- Модель решает задачу «в уме» и вызывает `finish`, не делая реальных шагов (read_file, create_file, run_terminal_cmd и т.д.).
- Модель вызывает `finish` без параметра `output` или с пустым `output`.
- Мало итераций / жёсткий лимит шагов — модель не успевает дойти до create_file и сразу переходит к finish.

---

## Итог: архитектура vs исполнение

| Уровень | Работает? | Комментарий |
|--------|-----------|-------------|
| Роутинг (Victoria → department_heads) | Да | Задача доходит до отдела и эксперта. |
| Выбор эксперта (Дмитрий и т.д.) | Да | Department Heads возвращает стратегию и expert_info. |
| Вызов ReActAgent | Да | `expert_agent.run(goal)` вызывается. |
| Исполнение внутри ReActAgent | Частично / нет | Модель не создаёт файлы и не кладёт результат в `finish.output`. |
| Формирование ответа пользователю | Да, но с пустым вводом | Код корректно берёт reflection/observation; т.к. они пустые — показывается fallback «статус: finish». |

То есть **архитектура обработки задач (маршрутизация, отделы, эксперты, вызов агента) работает**. Не работает то, что **агент (ReActAgent + LLM) не выполняет задачу до конца и не возвращает осмысленный результат** в `final_reflection` или в `output` действия `finish`.

---

## Что можно сделать

1. **Усилить промпт ReActAgent для экспертов**  
   Явно требовать: не вызывать `finish`, пока не выполнены инструменты (create_file / write_file и т.д.), и всегда передавать в `finish` параметр `output` с кратким описанием сделанного и, при необходимости, путями к файлам.

2. **Собирать результат из всех шагов**  
   Не только из последнего шага: если в цепочке были `create_file` / `write_file`, брать из их `observation` путь к файлу и фрагмент контента и подставлять это в итоговый текст для пользователя (в дополнение к `final_reflection` и `finish.output`).

3. **Требовать output у finish**  
   В коде ReActAgent при действии `finish`: если `output` и `result` пустые — не считать шаг успешным завершением, а вернуть наблюдение вида «Задача не завершена: finish вызван без output» и дать агенту ещё одну итерацию (или явно сообщить пользователю «модель не вернула результат»).

4. **Лимиты и поощрение использования инструментов**  
   Увеличить max_iterations для задач типа «создать код/файл» и добавить в system_prompt правило: для задач на создание артефакта обязательно использовать create_file/write_file, а не только ответ в reflection.

5. **Верификация перед ответом пользователю**  
   В `_execute_department_task`: если после `expert_agent.run()` результат пустой или равен подставной строке «Задача выполнена экспертом … (статус: finish)», не возвращать это как успех, а либо повторить запуск с уточнённым промптом, либо вернуть честное сообщение: «Эксперт завершил задачу без вывода; попробуйте переформулировать или разбить задачу».

Если хочешь, можно следующий шаг сделать конкретно по коду: куда в `victoria_enhanced` и `react_agent` вставить проверку `finish.output` и сбор результата из шагов с create_file/write_file.

---

## Внесённые исправления

1. **ReActAgent: сохранение output действия finish в шаге** — `knowledge_os/app/react_agent.py`: при `action == "finish"` у созданного шага сразу задаётся `step.observation` из `action_input.output`/`result`, чтобы результат попадал в возвращаемый `_build_result()` и в Victoria Enhanced из последнего шага.
2. **ReActAgent: не считать finish без output завершением** — `knowledge_os/app/react_agent.py`: если модель вызвала `finish` без `output`/`result` и лимит итераций не исчерпан, цикл не завершается; в observation шага пишется требование вызвать finish с параметром output, цикл продолжается.
3. **Victoria Enhanced: сбор результата из шагов create_file/write_file** — `knowledge_os/app/victoria_enhanced.py` в `_execute_department_task`: после извлечения результата из `final_reflection` и последнего шага выполняется агрегация по `result_dict["steps"]` для шагов с `action in ("create_file", "write_file")`; их `observation` собираются в одну строку (лимит 12 КБ); если результат пустой или подставной — используется агрегированный текст.
4. **Victoria Enhanced: не отдавать «пустой успех»** — `knowledge_os/app/victoria_enhanced.py`: если результат равен подставной строке «Задача выполнена экспертом … (статус: finish)», пользователю возвращается честное сообщение: «Эксперт завершил задачу без вывода (модель вызвала finish без результата). Попробуйте переформулировать задачу или разбить на подзадачи.»
5. **ReActAgent: промпт — требовать output у finish и ключевые слова** — `knowledge_os/app/react_agent.py`: в `_build_act_prompt` и `_build_think_prompt` у инструмента finish указано «output (обязательный …). Не вызывай finish без output»; расширены списки ключевых слов для «требует создания файла» (в т.ч. «создай бота», «бота для телеграм», «aiogram», «пуллинг», «telegram bot»).
6. **Victoria Enhanced: усиление system_prompt эксперта** — `knowledge_os/app/victoria_enhanced.py` при создании ReActAgent для эксперта: в `expert_system_prompt` добавлен блок о необходимости использовать create_file/write_file для задач на код/файлы/ботов и всегда передавать в finish параметр output с описанием и путями к файлам.
