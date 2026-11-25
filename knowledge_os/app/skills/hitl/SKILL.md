---
name: hitl
description: Human-in-the-Loop - контроль человека для критичных операций (LangGraph, Anthropic)
category: safety
version: 1.1
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "👤",
        "homepage": "https://langchain-ai.github.io/langgraph/",
      },
  }
---

# Human-in-the-Loop Skill

Навык на основе **Human-in-the-Loop (HITL)** от LangGraph и Anthropic. Контроль человека для критичных операций.

## Когда использовать

- Критичные операции (удаление, изменение важных файлов, git mutate, MCP write)
- Операции с высоким риском
- Решения, требующие одобрения
- Задачи с неопределенностью

## Методология

1. **Risk Assessment** — оценка риска операции
2. **Human Request** — запрос одобрения у человека
3. **Wait for Approval** — ожидание одобрения
4. **Execution** — выполнение только после одобрения
5. **Logging** — логирование всех операций

## Done = verified (gate)

HITL **не done**, пока нет явного approve:

| Шаг     | Пруф                                                        |
| ------- | ----------------------------------------------------------- |
| Запрос  | текст риска + что именно будет изменено (пути)              |
| Approve | `approve_writes=true` / ответ пользователя «да» / env allow |
| Execute | diff/stat/exit code после действия                          |
| Deny    | файл **не** изменился; ответ `REJECTED` / unchanged         |

Без approve писать в репо / удалять / `git commit` — **запрещено**.  
«Сделаю потом» без пруфа отказа/аппрува — не HITL.

Связь runtime: `execution_plan_local` + `ATRA_ALLOW_GIT_MUTATE` fail-closed + `hitl.py`.

## Пример

```
Операция: Удаление базы данных

HITL:
1. Оценка: Высокий риск
2. Запрос: "Вы уверены, что хотите удалить БД?"
3. Ожидание: Ответ пользователя
4. Выполнение: Только после подтверждения
5. Пруф: лог + статус
```

## Источник

- LangGraph HITL / Anthropic Safety
- Файл: `knowledge_os/app/hitl.py`
- ECC-идея: stop-hooks / permission before mutate
