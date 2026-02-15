---
name: incremental-file-editing
description: Surgical file editing using patches instead of full rewrites.
category: coding
author: AI Research KB (OpenAI)
version: 1.0
---

# Skill: Incremental File Editing (apply_patch)
# Source: AI Research KB (OpenAI Codex, GPT-5 Agent Mode)

## Description
Метод хирургического редактирования файлов через патчи вместо полной перезаписи. Экономит токены, снижает риск ошибок синтаксиса и ускоряет работу с кодом.

## Methodology
1. **Surgical Precision**: Используй `apply_patch` для внесения изменений. Не переписывай весь файл, если нужно изменить одну функцию.
2. **Patch Format**:
   ```
   *** Begin Patch
   *** Update File: path/to/file.py
   @@ function_name():
   - old_code_line
   + new_code_line
   *** End Patch
   ```
3. **Progress Updates**: Перед началом крупной операции (рефакторинг > 3 файлов) отправь короткое сообщение (8-10 слов) о текущем прогрессе.
4. **Tool Trust**: Если инструмент не вернул ошибку, считай патч примененным. Не перечитывай файл (`read_file`) без явной необходимости.

## Examples
- "Обновляю логику валидации в auth.py..." -> [apply_patch]
- "Исправляю опечатку в заголовке README.md..." -> [apply_patch]
