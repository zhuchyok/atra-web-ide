---
name: Fast Track Optimization
description: Процедура ускорения ответов через Semantic Router и Fast Track
category: performance
version: 1.0.0
author: Victoria AI
---

# Fast Track Optimization

## Когда использовать

Процедура ускорения ответов через Semantic Router и Fast Track

## Процедура

1. Проверить запрос через SemanticRouter.
2. Если категория fast_track/info/vip - использовать lfm2.5-thinking.
3. Использовать кэш Redis с продлением TTL.
4. Поддерживать Pulse прогрев моделей.

## Проверка (Verification)

Отклик на 'привет' < 500мс
