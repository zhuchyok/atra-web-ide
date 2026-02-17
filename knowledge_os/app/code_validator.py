"""
CodeValidator — инструменты для предполетной проверки кода.
[SINGULARITY 14.3] Предотвращение технического паралича через проверку синтаксиса и импортов.
"""
import ast
import logging
import sys
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class CodeValidator:
    """Валидатор кода для предотвращения критических ошибок при записи."""

    @staticmethod
    def validate_python(content: str, filename: str = "<string>") -> Dict[str, Any]:
        """
        Проверяет Python код на синтаксические ошибки и базовые проблемы с импортами.
        
        Returns:
            Dict с ключами:
                success: bool
                error: Optional[str]
                line: Optional[int]
                column: Optional[int]
        """
        try:
            # 1. Синтаксический анализ
            tree = ast.parse(content, filename=filename)
            
            # 2. Проверка на NameError (базовая)
            # Мы не можем проверить все NameError без выполнения, 
            # но можем найти очевидные пропущенные импорты для стандартных типов,
            # которые часто вызывают падения (Dict, List, Any, uuid и т.д.)
            
            # Собираем все используемые имена
            used_names = set()
            defined_names = set()
            imported_names = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    if isinstance(node.context, ast.Load):
                        used_names.add(node.id)
                    elif isinstance(node.context, ast.Store):
                        defined_names.add(node.id)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imported_names.add(alias.asname or alias.name)
                elif isinstance(node, ast.FunctionDef):
                    defined_names.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    defined_names.add(node.name)
                elif isinstance(node, ast.arg):
                    defined_names.add(node.arg)

            # Встроенные имена
            builtin_names = set(dir(__builtins__))
            
            # Критически важные имена, которые часто забывают импортировать
            critical_missing = []
            common_types = {'Dict', 'List', 'Any', 'Optional', 'Union', 'Callable', 'Iterable', 'TypeVar', 'Generic'}
            common_modules = {'uuid', 'json', 'os', 'sys', 'time', 'datetime', 'asyncio'}
            
            for name in used_names:
                if name not in defined_names and name not in imported_names and name not in builtin_names:
                    if name in common_types or name in common_modules:
                        critical_missing.append(name)

            if critical_missing:
                msg = f"Критическая ошибка: Использованы, но не импортированы: {', '.join(critical_missing)}"
                logger.error(f"CodeValidator: {msg} in {filename}")
                return {
                    "success": False,
                    "error": msg,
                    "type": "ImportError"
                }

            return {"success": True}

        except SyntaxError as e:
            logger.error(f"CodeValidator: SyntaxError in {filename}: {e.msg} at line {e.lineno}")
            return {
                "success": False,
                "error": f"SyntaxError: {e.msg}",
                "line": e.lineno,
                "column": e.offset,
                "type": "SyntaxError"
            }
        except Exception as e:
            logger.exception(f"CodeValidator: Непредвиденная ошибка при валидации {filename}")
            return {
                "success": False,
                "error": f"Validation error: {str(e)}",
                "type": "UnknownError"
            }

    @staticmethod
    def is_python_file(filepath: str) -> bool:
        """Проверяет, является ли файл Python-скриптом."""
        return filepath.endswith('.py')
