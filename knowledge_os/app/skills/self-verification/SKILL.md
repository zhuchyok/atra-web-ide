---
name: self-verification
description: Mandatory self-checking protocol to eliminate hallucinations and logical errors.
category: quality
author: AI Research KB (OpenAI o1)
version: 1.0
---

# Skill: Self-Verification Protocol
# Source: AI Research KB (OpenAI o1/o3 Pattern)

## Description
Протокол принудительной проверки собственных выводов для исключения галлюцинаций и логических ошибок.

## Methodology
1. **Digit-by-Digit Arithmetic**: При выполнении математических расчетов считай по цифрам, записывая промежуточные шаги. Никогда не полагайся на интуитивный ответ модели.
2. **Adversarial Thinking**: При получении вопросов с подвохом или логических загадок, предполагай, что формулировка намеренно вводит в заблуждение. Проверь каждое слово.
3. **Temporal Verification**: Если факт может измениться со временем (цены, версии ПО, новости), всегда используй веб-поиск, даже если уверен в ответе.
4. **Uncertainty Trigger**: Если пользователь спрашивает «Ты уверен?», немедленно запусти полный цикл верификации через альтернативного эксперта или веб-поиск.

## Examples
- "Сколько будет 1234 * 5678?" -> [Step-by-step calculation in Analysis]
- "Какая сейчас последняя версия Python?" -> [Web Search mandatory]
