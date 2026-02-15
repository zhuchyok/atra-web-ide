import os
import re
from typing import Dict, List, Optional

def get_file_skeleton(file_path: str) -> str:
    """
    Создает 'скелет' файла: оставляет только импорты, определения классов и функций.
    Тела функций заменяются на '... (код функции, N строк)'.
    Это позволяет LLM понять структуру 3000-строчного файла, не перегружая память.
    """
    if not os.path.exists(file_path):
        return f"Файл {file_path} не найден."

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        return f"Ошибка чтения файла: {e}"

    skeleton = []
    current_block = []
    in_function = False
    indent_level = 0
    func_start_line = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        
        # Сохраняем импорты и константы (на нулевом отступе)
        if (line.startswith(('import ', 'from ', 'st.', 'APP_', 'DB_')) or 
            (not line.startswith(' ') and '=' in line and not line.startswith('def '))):
            if not in_function:
                skeleton.append(line.rstrip())
            continue

        # Детекция начала функции или класса
        if line.startswith(('def ', 'class ')) or re.match(r'^\s+(def|class) ', line):
            if in_function:
                # Закрываем предыдущую функцию
                skeleton.append(f"{' ' * indent_level}    ... (код блока, {i - func_start_line} строк)")
            
            skeleton.append(line.rstrip())
            in_function = True
            indent_level = len(line) - len(line.lstrip())
            func_start_line = i
            continue

        # Если мы внутри функции и вернулись на уровень отступа функции или выше
        if in_function and stripped and not line.startswith(' ' * (indent_level + 1)):
            if not line.startswith('@'): # Игнорируем декораторы как конец блока
                skeleton.append(f"{' ' * indent_level}    ... (код блока, {i - func_start_line} строк)")
                skeleton.append(line.rstrip())
                in_function = False

    if in_function:
        skeleton.append(f"{' ' * indent_level}    ... (последний блок, {len(lines) - func_start_line} строк)")

    return "\n".join(skeleton)

def extract_function_body(file_path: str, function_name: str) -> Optional[str]:
    """Извлекает тело конкретной функции для точечного рефакторинга."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return None

    body = []
    in_target = False
    indent = 0
    
    for line in lines:
        if f"def {function_name}" in line:
            in_target = True
            indent = len(line) - len(line.lstrip())
            body.append(line)
            continue
        
        if in_target:
            current_indent = len(line) - len(line.lstrip())
            if stripped := line.strip():
                if current_indent <= indent and not line.startswith('@'):
                    break
            body.append(line)
            
    return "".join(body) if body else None
