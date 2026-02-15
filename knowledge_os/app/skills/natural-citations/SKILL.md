---
name: natural-citations
description: Seamless integration of knowledge base references into agent responses.
category: communication
author: AI Research KB (Claude Opus)
version: 1.0
---

# Skill: Natural Citations (Seamless Integration)
# Source: AI Research KB (GPT-5.2 Thinking, Claude Opus)

## Description
Метод бесшовного вплетения ссылок на базу знаний в ответы для повышения авторитетности и проверяемости данных.

## Methodology
1. **Turn:Chunk Format**: Используй формат `[T:C]` для ссылок. Например, `[4:13]` означает 4-й ход диалога, 13-й чанк знаний.
2. **Contextual Weaving**: Вплетай цитаты в предложение. Вместо "Вот список источников в конце", пиши "Согласно мировым практикам [4:13], хирургическое редактирование предпочтительнее...".
3. **Semantic Anchors**: Каждая ссылка должна вести на конкретный факт, а не на весь документ.
4. **Strict Relevance**: Используй только те цитаты, которые напрямую подтверждают твой тезис.

## Examples
- "Как показано в исследовании Anthropic [2:5], обрезка контекста повышает точность на 40%."
