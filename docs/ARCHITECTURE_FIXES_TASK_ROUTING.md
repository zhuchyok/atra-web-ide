# Исправления архитектуры: маршрутизация и безопасность

## Что внедрено

### 1. Детектор типа задачи (`src/agents/bridge/task_detector.py`)

- **`detect_task_type(goal, context)`** — возвращает: `simple_chat` | `veronica` | `department_heads` | `enhanced`.
- **`should_use_enhanced(goal, project_context, use_enhanced_env)`** — при `USE_VICTORIA_ENHANCED=true` для запросов типа **simple_chat** (привет, пока, кто ты и т.п.) возвращает **False**, чтобы не поднимать тяжёлый Enhanced и отвечать быстрее через `agent.run()`.

**Ключевые слова:**
- **simple_chat:** привет, здравствуй, как дела, спасибо, пока, кто ты и т.д.
- **veronica:** выполни, сделай, напиши код, исправь, запусти, протестируй и т.д.
- **department_heads:** проанализируй, разработай стратегию, оптимизируй, спроектируй и т.д.
- **enhanced:** всё остальное (сложные комплексные задачи).

### 2. Маршрутизатор Veronica (`src/agents/bridge/enhanced_router.py`)

- **`delegate_to_veronica(goal, project_context, correlation_id)`** — прямой HTTP POST на `VERONICA_URL/run` (по умолчанию `http://localhost:8011/run`). Используется при `task_type == "veronica"` для быстрого делегирования без входа в Enhanced.
- Переменные окружения: `VERONICA_URL`, `DELEGATE_VERONICA_TIMEOUT` (по умолчанию 60 с).

### 3. Использование в `victoria_server.py`

- **Синхронный путь:** после уточнений вычисляется `task_type = detect_task_type(...)` и `use_enhanced_for_request`. При **task_type == "veronica"** сначала вызывается `delegate_to_veronica()`; при успешном ответе возвращается результат Veronica, иначе — переход в Enhanced.
- **simple_chat:** Enhanced не вызывается, ответ через `agent.run()`.
- **veronica:** попытка делегирования по HTTP; при успехе — ответ Veronica, иначе — Enhanced.
- **department_heads / enhanced:** как раньше, через Victoria Enhanced.
- **Асинхронный путь (202):** в `_run_task_background` в начале вычисляется `use_enhanced_actual = should_use_enhanced(goal, project_context, use_enhanced)` и дальше используется оно.
- В лог пишется тип задачи и флаг use_enhanced: `Запрос [correlation_id] тип: veronica, use_enhanced: True`.

### 4. Санитайзер целей (`_sanitize_goal_for_prompt`)

- Перед передачей цели в `agent.run()` и `enhanced.solve()` текст цели очищается от упоминаний несуществующих инструментов: **web_search**, **swarm_intelligence**, **consensus**, **tree_of_thoughts**, **psych_assessment**, **patient_interview**, **therapy_technique**, **ethical_dilemma**, **empathetic_communication**, **web_edit**, **git_run**, **web_review**, **web_check**, **git_commit**, **websocket**. Они заменяются на `[инструмент недоступен]`, чтобы модель не подхватывала их в ответе.

### 5. Безопасность команд (`src/agents/tools/system_tools.py`)

- В **`_validate_command_safety`** добавлены паттерны: `chmod 777`, `sudo rm`, `sudo dd`, `mkfs.*`, `> /dev/`, `| rm `.
- Добавлена проверка на деструктивные операции с системными путями: если в команде есть **rm**, **mv**, **chmod**, **chown** и путь типа `/etc/`, `/bin/`, `/sbin/`, `/usr/bin/`, `/root/` — команда отклоняется.

## Что не делали (сознательно)

- **Прямой вызов Department Heads из run_task** по типу `department_heads` не добавляли: при `use_enhanced=true` такие задачи продолжают идти в Enhanced, где уже используется department_heads. Выделенный маршрут «только Department Heads» без Enhanced можно добавить отдельно.
- **Отдельный класс ToolValidator** не вводили: список разрешённых инструментов остаётся в **`src/agents/core/executor.py`** (`ALLOWED_TOOLS`). Валидация вызова инструмента по-прежнему там.
- **Отдельный PromptSanitizer в knowledge_os** не создавали: санитизация цели делается в `victoria_server.py` функцией `_sanitize_goal_for_prompt`; системный промпт исполнителя уже жёстко ограничивает инструменты (executor.py).

## Ожидаемый эффект

1. **Приветствия** («привет», «пока») — быстрый ответ через `agent.run()` без Enhanced.
2. **Меньше галлюцинаций по инструментам** — в цель не попадают названия несуществующих инструментов.
3. **Безопасность** — расширенная блокировка опасных команд и операций с системными путями.
4. **Логи** — видно тип задачи и решение use_enhanced по correlation_id.

## Проверка

```bash
# Тест детектора типов
python3 scripts/test_task_detector.py

# В чате с Victoria
привет          # → тип simple_chat, use_enhanced: False (если env=true)
напиши код      # → тип veronica: сначала POST на Veronica; при успехе — ответ Veronica
проанализируй   # → тип department_heads, use_enhanced: true
```

В логах Victoria при запросе должна быть строка вида:  
`Запрос [xxxxxxxx] тип: veronica, use_enhanced: True` или `Делегирую Veronica: ...`.
