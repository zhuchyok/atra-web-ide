---
name: self-verification
description: Mandatory self-checking protocol to eliminate hallucinations and logical errors. Done only with evidence.
category: quality
author: AI Research KB (OpenAI o1) + ECC done-gate
version: 1.1
---

# Skill: Self-Verification Protocol

# Source: AI Research KB (OpenAI o1/o3 Pattern) + harness done-gate

## Description

Протокол принудительной проверки собственных выводов для исключения галлюцинаций и логических ошибок.

## Methodology

1. **Digit-by-Digit Arithmetic**: При выполнении математических расчетов считай по цифрам, записывая промежуточные шаги. Никогда не полагайся на интуитивный ответ модели.
2. **Adversarial Thinking**: При получении вопросов с подвохом или логических загадок, предполагай, что формулировка намеренно вводит в заблуждение. Проверь каждое слово.
3. **Temporal Verification**: Если факт может измениться со временем (цены, версии ПО, новости), всегда используй веб-поиск, даже если уверен в ответе.
4. **Uncertainty Trigger**: Если пользователь спрашивает «Ты уверен?», немедленно запусти полный цикл верификации через альтернативного эксперта или веб-поиск.
5. **Evidence Replay**: Перед финалом перескажи _только_ то, что подтверждено инструментом (path, exit code, метрика). Всё остальное пометь `UNVERIFIED`.
6. **Fresh-pass review** (ECC): на нетривиальном diff сделай второй проход «как ревьюер» — 3 риска / что сломается / как откатить. Без второго прохода код-задачу не закрывай.

## Done gate

Перед «готово» ответь себе тремя строками:

```text
CLAIM: …
EVIDENCE: <команда или путь> → <факт из вывода>
FAIL_IF_MISSING: <что отсутствовало бы при выдумке>
```

Нет `EVIDENCE` → ответ не финальный.

## Examples

- "Сколько будет 1234 \* 5678?" -> [Step-by-step calculation in Analysis]
- "Какая сейчас последняя версия Python?" -> [Web Search mandatory]
- "965 passed" -> [pytest/CI log path mandatory; else UNVERIFIED]
