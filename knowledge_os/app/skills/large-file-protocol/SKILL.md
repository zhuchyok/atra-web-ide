---
name: large-file-protocol
description: Strategies for handling massive files (10k+ lines) without context overflow.
category: system
author: AI Research KB (Anthropic)
version: 1.0
---

# Skill: Large File Protocol
# Source: AI Research KB (Anthropic Claude, OpenAI Codex)

## Description
Стратегия работы с гигантскими файлами (10 000+ строк) без переполнения контекста и потери производительности.

## Methodology
1. **Detection**: Если файл превышает 2000 строк, пометь его как "Large".
2. **Programmatic Access**: Не пытайся прочитать весь файл целиком. Используй инструменты поиска (`grep`, `rg`) или читай только нужные диапазоны строк.
3. **Chunk Processing**: Разбей задачу на части. Сначала проанализируй структуру (скелет), затем работай с конкретным блоком.
4. **Heartbeat Updates**: При работе с большими данными присылай статус каждые 30 секунд, чтобы подтвердить, что процесс не завис.

## Examples
- "Анализирую структуру лог-файла (500MB)..." -> [Read first 100 lines + tail]
- "Ищу утечку памяти в ядре..." -> [Grep search for specific patterns]
