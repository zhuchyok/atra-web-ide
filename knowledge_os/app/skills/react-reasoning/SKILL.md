---
name: react-reasoning
description: ReAct Framework - Reasoning + Acting цикл для решения сложных задач
category: reasoning
version: 1.0.0
author: ATRA Corporation
metadata:
  {
    "clawdbot":
      {
        "requires": {},
        "emoji": "🧠",
        "homepage": "https://react-lm.github.io/",
      },
  }
---

# ReAct Reasoning Skill

Навык на основе **ReAct Framework** (Reasoning + Acting) от исследователей из Google и Princeton. Обеспечивает +30-40% улучшение качества решения задач.

## Когда использовать

Используй этот навык для:

- Сложных многошаговых задач
- Задач, требующих использования инструментов (файлы, команды, поиск)
- Задач, где нужно рассуждать перед действием
- Планирования и выполнения последовательности действий

## Методология

ReAct Framework работает по циклу:

1. **Reasoning** - Рассуждение о текущей ситуации
2. **Acting** - Выполнение действия через инструмент
3. **Observing** - Наблюдение результата
4. **Repeat** - Повторение до достижения цели

## Примеры использования

```
Пользователь: "Создай файл test.py с функцией hello() и запусти его"

Reasoning: "Мне нужно создать файл с функцией hello(), затем выполнить его.
Использую инструмент create_file для создания, затем run_terminal_cmd для запуска."

Action: create_file(file_path="test.py", content="def hello():\n    print('Hello!')\n\nif __name__ == '__main__':\n    hello()")
Observation: Файл создан успешно

Action: run_terminal_cmd(command="python test.py")
Observation: Hello!

Result: Задача выполнена успешно
```

## Интеграция

Этот навык автоматически активируется через `react_agent.py` когда задача требует использования инструментов.

## Источник

- ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al., 2022)
- Файл: `knowledge_os/app/react_agent.py`
