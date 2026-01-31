"""
Editor Router - AI автодополнение и linting для редактора
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import logging
import os

from app.services.victoria import VictoriaClient, get_victoria_client
from app.services.ollama import OllamaClient, get_ollama_client

logger = logging.getLogger(__name__)
router = APIRouter()


class AutocompleteRequest(BaseModel):
    """Запрос на автодополнение"""
    code: str = Field(..., description="Код до курсора")
    filename: str = Field(..., description="Имя файла")
    line: int = Field(..., description="Номер строки")
    column: int = Field(..., description="Позиция в строке")
    language: Optional[str] = Field(default=None, description="Язык программирования")


class AutocompleteResponse(BaseModel):
    """Ответ с автодополнениями"""
    completions: List[Dict[str, str]] = Field(..., description="Список автодополнений")
    # Формат: [{"label": "function_name", "type": "function", "detail": "описание", "insert": "function_name()"}]


class LintRequest(BaseModel):
    """Запрос на linting"""
    code: str = Field(..., description="Код для проверки")
    filename: str = Field(..., description="Имя файла")
    language: Optional[str] = Field(default=None, description="Язык программирования")


class LintResponse(BaseModel):
    """Ответ с ошибками linting"""
    errors: List[Dict[str, str | int]] = Field(..., description="Список ошибок")
    # Формат: [{"line": 1, "column": 5, "message": "ошибка", "severity": "error|warning|info"}]


@router.post("/autocomplete", response_model=AutocompleteResponse)
async def get_autocomplete(
    request: AutocompleteRequest,
    victoria: VictoriaClient = Depends(get_victoria_client)
) -> AutocompleteResponse:
    """
    Получить AI автодополнение для кода
    
    Использует Victoria для генерации автодополнений на основе контекста
    """
    try:
        # Определяем язык по расширению файла
        ext = ''
        if '.' in request.filename:
            parts = request.filename.split('.')
            if parts:
                ext = parts[-1].lower()
        language_map = {
            'py': 'Python',
            'js': 'JavaScript',
            'ts': 'TypeScript',
            'jsx': 'JavaScript',
            'tsx': 'TypeScript',
            'html': 'HTML',
            'css': 'CSS',
            'json': 'JSON',
            'md': 'Markdown'
        }
        language = request.language or language_map.get(ext, '')
        
        # Формируем промпт для автодополнения
        context_lines = request.code.split('\n')
        current_line = context_lines[-1] if context_lines else ''
        before_cursor = current_line[:request.column] if request.column <= len(current_line) else current_line
        
        # Берем контекст (последние 20 строк)
        context = '\n'.join(context_lines[-20:])
        
        prompt = f"""Ты AI-ассистент для автодополнения кода.

Язык: {language}
Файл: {request.filename}
Строка {request.line}, позиция {request.column}

Контекст кода:
```{language.lower()}
{context}
```

Текущая строка до курсора: `{before_cursor}`

Предложи 3-5 наиболее вероятных автодополнений для текущей позиции.
Формат ответа (только JSON, без текста):
{{
  "completions": [
    {{"label": "название", "type": "function|variable|keyword|class", "detail": "краткое описание", "insert": "текст для вставки"}},
    ...
  ]
}}

Важно:
- Предлагай только релевантные автодополнения
- Учитывай контекст кода
- Для функций добавляй скобки если нужно
- Будь кратким и точным
"""
        
        # Используем Victoria для генерации автодополнений
        result = await victoria.run(
            prompt=prompt,
            project_context=os.getenv("PROJECT_NAME", "atra-web-ide")
        )
        
        # Парсим ответ
        output = result.get("output", "")
        
        # Пытаемся извлечь JSON из ответа
        import json
        import re
        
        # Ищем JSON в ответе
        json_match = re.search(r'\{.*"completions".*\}', output, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                completions = data.get("completions", [])
            except:
                completions = []
        else:
            # Fallback: простые автодополнения на основе контекста
            completions = _generate_simple_completions(before_cursor, language)
        
        return AutocompleteResponse(completions=completions)
    
    except Exception as e:
        logger.error(f"Autocomplete error: {e}", exc_info=True)
        # Возвращаем пустой список при ошибке
        return AutocompleteResponse(completions=[])


def _generate_simple_completions(before_cursor: str, language: str) -> List[Dict[str, str]]:
    """Генерация простых автодополнений на основе контекста"""
    completions = []
    
    # Python
    if language.lower() == 'python':
        if 'def ' in before_cursor or 'class ' in before_cursor:
            completions.append({"label": "pass", "type": "keyword", "detail": "pass statement", "insert": "pass"})
        if 'import ' in before_cursor:
            completions.append({"label": "os", "type": "module", "detail": "OS module", "insert": "os"})
            completions.append({"label": "json", "type": "module", "detail": "JSON module", "insert": "json"})
    
    # JavaScript
    elif language.lower() in ['javascript', 'typescript']:
        if 'function ' in before_cursor or 'const ' in before_cursor or 'let ' in before_cursor:
            completions.append({"label": "() => {}", "type": "snippet", "detail": "Arrow function", "insert": "() => {}"})
        if 'console.' in before_cursor:
            completions.append({"label": "log", "type": "function", "detail": "console.log()", "insert": "log()"})
    
    return completions


@router.post("/lint", response_model=LintResponse)
async def lint_code(
    request: LintRequest
) -> LintResponse:
    """
    Проверить код на ошибки (linting)
    
    Использует встроенные проверки для разных языков
    """
    try:
        errors = []
        
        # Определяем язык
        ext = ''
        if '.' in request.filename:
            parts = request.filename.split('.')
            if parts:
                ext = parts[-1].lower()
        language = request.language or ext
        
        # Python linting (базовая проверка синтаксиса)
        if language.lower() == 'python':
            errors.extend(_lint_python(request.code))
        
        # JavaScript linting (базовая проверка)
        elif language.lower() in ['javascript', 'typescript']:
            errors.extend(_lint_javascript(request.code))
        
        # JSON linting
        elif language.lower() == 'json':
            errors.extend(_lint_json(request.code))
        
        return LintResponse(errors=errors)
    
    except Exception as e:
        logger.error(f"Lint error: {e}", exc_info=True)
        return LintResponse(errors=[])


def _lint_python(code: str) -> List[Dict[str, str | int]]:
    """Базовая проверка Python кода"""
    errors = []
    lines = code.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Проверка на табы (должны быть пробелы)
        if '\t' in line:
            errors.append({
                "line": i,
                "column": line.index('\t') + 1,
                "message": "Tab character found. Use spaces instead.",
                "severity": "warning"
            })
        
        # Проверка на неиспользуемые импорты (базовая)
        if line.strip().startswith('import ') or line.strip().startswith('from '):
            # Простая проверка - если импорт не используется в коде
            import_name = line.split()[1].split('.')[0] if len(line.split()) > 1 else ''
            if import_name and import_name not in code.replace(line, ''):
                errors.append({
                    "line": i,
                    "column": 1,
                    "message": f"Possibly unused import: {import_name}",
                    "severity": "info"
                })
    
    return errors


def _lint_javascript(code: str) -> List[Dict[str, str | int]]:
    """Базовая проверка JavaScript кода"""
    errors = []
    lines = code.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Проверка на == вместо ===
        if ' == ' in line and ' === ' not in line:
            errors.append({
                "line": i,
                "column": line.index(' == ') + 1,
                "message": "Use === instead of == for strict equality",
                "severity": "warning"
            })
        
        # Проверка на var вместо const/let
        if ' var ' in line:
            errors.append({
                "line": i,
                "column": line.index(' var ') + 1,
                "message": "Use const or let instead of var",
                "severity": "warning"
            })
    
    return errors


def _lint_json(code: str) -> List[Dict[str, str | int]]:
    """Проверка JSON синтаксиса"""
    errors = []
    
    try:
        import json
        json.loads(code)
    except json.JSONDecodeError as e:
        errors.append({
            "line": e.lineno,
            "column": e.colno,
            "message": f"JSON syntax error: {e.msg}",
            "severity": "error"
        })
    
    return errors
