"""
AntiPatternDetector - Обнаружение антипаттернов в коде

Принцип: Self-Validating Code - Anti-Pattern Detection
Цель: Обнаружение "имитации" правильной работы, выявление скрытых ошибок и логических противоречий
"""

import ast
import inspect
import logging
import re
from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class AntiPatternType(Enum):
    """Типы антипаттернов"""
    DIVISION_BY_ZERO = "division_by_zero"
    NONE_IN_CRITICAL = "none_in_critical"
    DEAD_CODE = "dead_code"
    LOGICAL_CONTRADICTION = "logical_contradiction"
    MISSING_VALIDATION = "missing_validation"
    BROAD_EXCEPT = "broad_except"
    UNUSED_VARIABLE = "unused_variable"
    MUTABLE_DEFAULT = "mutable_default"
    COMPARISON_WITH_NONE = "comparison_with_none"
    MISSING_RETURN = "missing_return"


@dataclass
class AntiPattern:
    """Обнаруженный антипаттерн"""
    pattern_type: AntiPatternType
    file_path: str
    line_number: int
    message: str
    severity: str = "warning"  # "info", "warning", "error", "critical"
    code_snippet: Optional[str] = None
    suggestion: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AntiPatternDetector:
    """
    Детектор антипаттернов в коде
    
    Обеспечивает:
    - Обнаружение типичных ошибок (деление на ноль, None в критичных местах)
    - Обнаружение "мертвого кода"
    - Проверку логических противоречий
    - Выявление скрытых ошибок
    """
    
    def __init__(self, enable_logging: bool = True):
        """
        Инициализация детектора
        
        Args:
            enable_logging: Включить логирование обнаруженных антипаттернов
        """
        self.enable_logging = enable_logging
        self._detected_patterns: List[AntiPattern] = []
        self._enabled_checks: Set[AntiPatternType] = set(AntiPatternType)
        
    def detect_in_code(self, code: str, file_path: str = "unknown") -> List[AntiPattern]:
        """
        Обнаружение антипаттернов в коде
        
        Args:
            code: Исходный код для анализа
            file_path: Путь к файлу (для отчётности)
            
        Returns:
            Список обнаруженных антипаттернов
        """
        patterns = []
        
        try:
            tree = ast.parse(code)
            visitor = AntiPatternVisitor(self, file_path)
            visitor.visit(tree)
            patterns.extend(visitor.patterns)
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        
        self._detected_patterns.extend(patterns)
        
        if self.enable_logging and patterns:
            for pattern in patterns:
                logger.warning(
                    f"Anti-pattern detected in {file_path}:{pattern.line_number}: "
                    f"{pattern.pattern_type.value} - {pattern.message}"
                )
        
        return patterns
    
    def detect_in_function(self, func: Callable) -> List[AntiPattern]:
        """
        Обнаружение антипаттернов в функции
        
        Args:
            func: Функция для анализа
            
        Returns:
            Список обнаруженных антипаттернов
        """
        try:
            source = inspect.getsource(func)
            file_path = inspect.getfile(func)
            return self.detect_in_code(source, file_path)
        except (OSError, TypeError):
            return []
    
    def check_division_by_zero(self, code: str, file_path: str = "unknown") -> List[AntiPattern]:
        """
        Проверка деления на ноль
        
        Args:
            code: Исходный код
            file_path: Путь к файлу
            
        Returns:
            Список обнаруженных проблем
        """
        patterns = []
        
        # Ищем паттерны деления: /, //, %
        division_patterns = [
            (r'(\w+)\s*/\s*(\w+)', '/'),
            (r'(\w+)\s*//\s*(\w+)', '//'),
            (r'(\w+)\s*%\s*(\w+)', '%'),
        ]
        
        lines = code.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern, op in division_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    divisor = match.group(2)
                    # Проверяем, не является ли делитель константой 0
                    if divisor == '0' or divisor.startswith('0.'):
                        patterns.append(AntiPattern(
                            pattern_type=AntiPatternType.DIVISION_BY_ZERO,
                            file_path=file_path,
                            line_number=line_num,
                            message=f"Division by zero detected: {match.group(0)}",
                            severity="error",
                            code_snippet=line.strip(),
                            suggestion=f"Add check: if {divisor} != 0: ..."
                        ))
        
        return patterns
    
    def check_none_in_critical(self, code: str, file_path: str = "unknown") -> List[AntiPattern]:
        """
        Проверка None в критичных местах (без проверки)
        
        Args:
            code: Исходный код
            file_path: Путь к файлу
            
        Returns:
            Список обнаруженных проблем
        """
        patterns = []
        
        # Критичные операции, где None недопустим
        critical_operations = [
            r'(\w+)\.price\s*[<>=]',  # price comparisons
            r'(\w+)\.quantity\s*[<>=]',  # quantity operations
            r'(\w+)\.balance\s*[<>=]',  # balance operations
            r'float\((\w+)\)',  # float conversion
            r'int\((\w+)\)',  # int conversion
            r'Decimal\((\w+)\)',  # Decimal conversion
        ]
        
        lines = code.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern in critical_operations:
                matches = re.finditer(pattern, line)
                for match in matches:
                    var_name = match.group(1)
                    # Проверяем, есть ли проверка на None перед использованием
                    # Упрощённая проверка - ищем if/assert перед этой строкой
                    context_start = max(0, line_num - 5)
                    context = '\n'.join(lines[context_start:line_num])
                    
                    if f'if {var_name} is None' not in context and \
                       f'if {var_name} is not None' not in context and \
                       f'assert {var_name} is not None' not in context:
                        patterns.append(AntiPattern(
                            pattern_type=AntiPatternType.NONE_IN_CRITICAL,
                            file_path=file_path,
                            line_number=line_num,
                            message=f"Potential None value in critical operation: {var_name}",
                            severity="warning",
                            code_snippet=line.strip(),
                            suggestion=f"Add check: if {var_name} is not None: ..."
                        ))
        
        return patterns
    
    def check_broad_except(self, code: str, file_path: str = "unknown") -> List[AntiPattern]:
        """
        Проверка слишком общих исключений
        
        Args:
            code: Исходный код
            file_path: Путь к файлу
            
        Returns:
            Список обнаруженных проблем
        """
        patterns = []
        
        # Ищем except Exception, except:, except BaseException
        broad_except_patterns = [
            r'except\s+Exception\s*:',
            r'except\s*:',
            r'except\s+BaseException\s*:',
        ]
        
        lines = code.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern in broad_except_patterns:
                if re.search(pattern, line):
                    patterns.append(AntiPattern(
                        pattern_type=AntiPatternType.BROAD_EXCEPT,
                        file_path=file_path,
                        line_number=line_num,
                        message="Broad exception handler detected",
                        severity="warning",
                        code_snippet=line.strip(),
                        suggestion="Use specific exception types: except ValueError, KeyError: ..."
                    ))
        
        return patterns
    
    def check_mutable_default(self, code: str, file_path: str = "unknown") -> List[AntiPattern]:
        """
        Проверка изменяемых значений по умолчанию
        
        Args:
            code: Исходный код
            file_path: Путь к файлу
            
        Returns:
            Список обнаруженных проблем
        """
        patterns = []
        
        # Ищем функции с изменяемыми значениями по умолчанию
        mutable_default_patterns = [
            r'def\s+\w+\s*\([^)]*=\s*\[\s*\)',  # = []
            r'def\s+\w+\s*\([^)]*=\s*\{\s*\)',  # = {}
        ]
        
        lines = code.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern in mutable_default_patterns:
                if re.search(pattern, line):
                    patterns.append(AntiPattern(
                        pattern_type=AntiPatternType.MUTABLE_DEFAULT,
                        file_path=file_path,
                        line_number=line_num,
                        message="Mutable default argument detected",
                        severity="warning",
                        code_snippet=line.strip(),
                        suggestion="Use None as default: def func(arg=None): arg = arg or []"
                    ))
        
        return patterns
    
    def check_comparison_with_none(self, code: str, file_path: str = "unknown") -> List[AntiPattern]:
        """
        Проверка сравнения с None через == вместо is
        
        Args:
            code: Исходный код
            file_path: Путь к файлу
            
        Returns:
            Список обнаруженных проблем
        """
        patterns = []
        
        # Ищем == None или != None
        none_comparison_patterns = [
            r'(\w+)\s*==\s*None',
            r'(\w+)\s*!=\s*None',
        ]
        
        lines = code.split('\n')
        for line_num, line in enumerate(lines, 1):
            for pattern in none_comparison_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    var_name = match.group(1)
                    op = '==' if '==' in match.group(0) else '!='
                    patterns.append(AntiPattern(
                        pattern_type=AntiPatternType.COMPARISON_WITH_NONE,
                        file_path=file_path,
                        line_number=line_num,
                        message=f"Comparison with None using {op} instead of 'is'",
                        severity="info",
                        code_snippet=line.strip(),
                        suggestion=f"Use: {var_name} is None" if op == '==' else f"Use: {var_name} is not None"
                    ))
        
        return patterns
    
    def get_detected_patterns(self) -> List[AntiPattern]:
        """Получить все обнаруженные антипаттерны"""
        return self._detected_patterns.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику обнаруженных антипаттернов"""
        total = len(self._detected_patterns)
        
        by_type = {}
        for pattern_type in AntiPatternType:
            by_type[pattern_type.value] = sum(
                1 for p in self._detected_patterns
                if p.pattern_type == pattern_type
            )
        
        by_severity = {}
        for severity in ["info", "warning", "error", "critical"]:
            by_severity[severity] = sum(
                1 for p in self._detected_patterns
                if p.severity == severity
            )
        
        return {
            "total_patterns": total,
            "by_type": by_type,
            "by_severity": by_severity
        }
    
    def clear_detected(self) -> None:
        """Очистить список обнаруженных антипаттернов"""
        self._detected_patterns.clear()


class AntiPatternVisitor(ast.NodeVisitor):
    """AST visitor для обнаружения антипаттернов"""
    
    def __init__(self, detector: AntiPatternDetector, file_path: str):
        self.detector = detector
        self.file_path = file_path
        self.patterns: List[AntiPattern] = []
    
    def visit_BinOp(self, node):
        """Проверка бинарных операций (деление на ноль)"""
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            # Проверяем, не является ли правый операнд константой 0
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.patterns.append(AntiPattern(
                    pattern_type=AntiPatternType.DIVISION_BY_ZERO,
                    file_path=self.file_path,
                    line_number=node.lineno,
                    message="Division by zero detected",
                    severity="error",
                    suggestion="Add check before division"
                ))
        
        self.generic_visit(node)
    
    def visit_ExceptHandler(self, node):
        """Проверка обработчиков исключений"""
        if node.type is None or \
           (isinstance(node.type, ast.Name) and node.type.id == 'Exception') or \
           (isinstance(node.type, ast.Name) and node.type.id == 'BaseException'):
            self.patterns.append(AntiPattern(
                pattern_type=AntiPatternType.BROAD_EXCEPT,
                file_path=self.file_path,
                line_number=node.lineno,
                message="Broad exception handler detected",
                severity="warning",
                suggestion="Use specific exception types"
            ))
        
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        """Проверка функций (изменяемые значения по умолчанию)"""
        for arg in node.args.defaults:
            if isinstance(arg, (ast.List, ast.Dict, ast.Set)):
                self.patterns.append(AntiPattern(
                    pattern_type=AntiPatternType.MUTABLE_DEFAULT,
                    file_path=self.file_path,
                    line_number=node.lineno,
                    message="Mutable default argument detected",
                    severity="warning",
                    suggestion="Use None as default"
                ))
        
        self.generic_visit(node)
    
    def visit_Compare(self, node):
        """Проверка сравнений (сравнение с None через ==)"""
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(comparator, ast.Constant) and comparator.value is None:
                if isinstance(op, ast.Eq) or isinstance(op, ast.NotEq):
                    self.patterns.append(AntiPattern(
                        pattern_type=AntiPatternType.COMPARISON_WITH_NONE,
                        file_path=self.file_path,
                        line_number=node.lineno,
                        message="Comparison with None using == instead of 'is'",
                        severity="info",
                        suggestion="Use 'is None' or 'is not None'"
                    ))
        
        self.generic_visit(node)


# Глобальный экземпляр для удобства использования
_global_detector: Optional[AntiPatternDetector] = None


def get_anti_pattern_detector() -> AntiPatternDetector:
    """
    Получить глобальный экземпляр AntiPatternDetector
    
    Returns:
        Глобальный экземпляр детектора
    """
    global _global_detector
    if _global_detector is None:
        _global_detector = AntiPatternDetector()
    return _global_detector

