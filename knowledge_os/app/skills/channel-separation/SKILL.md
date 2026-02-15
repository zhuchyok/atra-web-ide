---
name: channel-separation
description: Separation of agent output into Analysis, Commentary, and Final channels.
category: reasoning
author: AI Research KB (OpenAI)
version: 1.0
---

# Skill: Channel Separation (Analysis/Commentary/Final)
# Source: AI Research KB (OpenAI o3, GPT-5 Thinking)

## Description
Разделение вывода агента на три изолированных канала для обеспечения чистоты и профессионализма ответов.

## Methodology
1. **Analysis Channel**: Используй этот канал для «внутреннего монолога», расчетов, написания кода и вызова инструментов. Этот контент скрыт от пользователя (Dual-channel).
2. **Commentary Channel**: Здесь описывай только действия инструментов (например, «Запускаю тесты...», «Читаю базу знаний...»).
3. **Final Channel**: Финальный, отполированный ответ. Никаких следов цепочки мыслей, только результат в строгом стиле.
4. **Strict Isolation**: Никогда не выводи технические детали (JSON, логи) в финальный канал, если пользователь об этом не просил.

## Examples
- [Analysis]: (скрыто) Расчет ROI...
- [Commentary]: Анализирую финансовые показатели...
- [Final]: Ваш ROI за текущий квартал составил 15%.
