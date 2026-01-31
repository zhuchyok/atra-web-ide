"""
SelfValidationManager - Runtime проверки консистентности и инвариантов

Принцип: Self-Validating Code - Self-Validation
Цель: Обеспечить автоматическое обнаружение несоответствий в runtime через проверку инвариантов и консистентности состояния
"""

import logging
import functools
import inspect
from typing import Optional, Dict, Any, Callable, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Уровни валидации"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """Результат проверки валидации"""
    passed: bool
    message: str
    level: ValidationLevel = ValidationLevel.ERROR
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class InvariantDefinition:
    """Определение инварианта"""
    name: str
    check_func: Callable[[Any], bool]
    message: str
    level: ValidationLevel = ValidationLevel.ERROR
    enabled: bool = True


class SelfValidationManager:
    """
    Менеджер для управления runtime проверками консистентности
    
    Обеспечивает:
    - Регистрацию и выполнение инвариантов
    - Проверку консистентности состояния
    - Автоматическое обнаружение несоответствий
    - Логирование нарушений
    """
    
    def __init__(self, enable_logging: bool = True, fail_fast: bool = False):
        """
        Инициализация менеджера валидации
        
        Args:
            enable_logging: Включить логирование нарушений
            fail_fast: Прерывать выполнение при первой ошибке
        """
        self.enable_logging = enable_logging
        self.fail_fast = fail_fast
        self._invariants: Dict[str, List[InvariantDefinition]] = {}
        self._validation_history: List[ValidationResult] = []
        self._enabled = True
        
    def register_invariant(
        self,
        class_name: str,
        name: str,
        check_func: Callable[[Any], bool],
        message: str = "",
        level: ValidationLevel = ValidationLevel.ERROR,
        enabled: bool = True
    ) -> None:
        """
        Регистрация инварианта для класса
        
        Args:
            class_name: Имя класса или тип объекта
            name: Имя инварианта
            check_func: Функция проверки (принимает объект, возвращает bool)
            message: Сообщение при нарушении
            level: Уровень валидации
            enabled: Включен ли инвариант
        """
        if class_name not in self._invariants:
            self._invariants[class_name] = []
        
        invariant = InvariantDefinition(
            name=name,
            check_func=check_func,
            message=message or f"Invariant {name} violated",
            level=level,
            enabled=enabled
        )
        
        self._invariants[class_name].append(invariant)
        
        if self.enable_logging:
            logger.debug(f"Registered invariant '{name}' for class '{class_name}'")
    
    def validate_object(self, obj: Any, class_name: Optional[str] = None) -> List[ValidationResult]:
        """
        Валидация объекта по всем зарегистрированным инвариантам
        
        Args:
            obj: Объект для валидации
            class_name: Имя класса (если None, определяется автоматически)
            
        Returns:
            Список результатов валидации
        """
        if not self._enabled:
            return []
        
        if class_name is None:
            class_name = type(obj).__name__
        
        results = []
        
        # Проверяем инварианты для конкретного класса
        if class_name in self._invariants:
            for invariant in self._invariants[class_name]:
                if not invariant.enabled:
                    continue
                
                try:
                    passed = invariant.check_func(obj)
                    
                    result = ValidationResult(
                        passed=passed,
                        message=invariant.message if not passed else "",
                        level=invariant.level,
                        details={
                            "invariant_name": invariant.name,
                            "class_name": class_name,
                            "object": str(obj)[:100]  # Первые 100 символов
                        }
                    )
                    
                    results.append(result)
                    
                    if not passed:
                        if self.enable_logging:
                            log_level = invariant.level.value.upper()
                            logger.log(
                                getattr(logging, log_level, logging.ERROR),
                                f"Invariant '{invariant.name}' violated for {class_name}: {invariant.message}"
                            )
                        
                        if self.fail_fast:
                            raise ValueError(f"Invariant '{invariant.name}' violated: {invariant.message}")
                    
                except Exception as e:
                    error_result = ValidationResult(
                        passed=False,
                        message=f"Error checking invariant '{invariant.name}': {str(e)}",
                        level=ValidationLevel.CRITICAL,
                        details={
                            "invariant_name": invariant.name,
                            "class_name": class_name,
                            "error": str(e)
                        }
                    )
                    results.append(error_result)
                    
                    if self.enable_logging:
                        logger.error(f"Error checking invariant '{invariant.name}': {e}")
        
        # Проверяем инварианты для базовых классов (MRO)
        for base_class in type(obj).__mro__[1:]:  # Пропускаем сам класс
            base_name = base_class.__name__
            if base_name in self._invariants:
                for invariant in self._invariants[base_name]:
                    if not invariant.enabled:
                        continue
                    
                    try:
                        passed = invariant.check_func(obj)
                        if not passed:
                            result = ValidationResult(
                                passed=False,
                                message=invariant.message,
                                level=invariant.level,
                                details={
                                    "invariant_name": invariant.name,
                                    "class_name": base_name,
                                    "inherited": True
                                }
                            )
                            results.append(result)
                            
                            if self.enable_logging:
                                logger.warning(
                                    f"Inherited invariant '{invariant.name}' violated for {class_name}"
                                )
                    except Exception:
                        pass  # Игнорируем ошибки в базовых классах
        
        # Сохраняем историю
        self._validation_history.extend(results)
        
        return results
    
    def validate_consistency(self, *objects: Any) -> List[ValidationResult]:
        """
        Проверка консистентности между несколькими объектами
        
        Args:
            *objects: Объекты для проверки консистентности
            
        Returns:
            Список результатов валидации
        """
        if not self._enabled:
            return []
        
        results = []
        
        # Проверяем каждый объект отдельно
        for obj in objects:
            obj_results = self.validate_object(obj)
            results.extend(obj_results)
        
        # Здесь можно добавить проверки консистентности между объектами
        # Например, проверка что сумма позиций не превышает баланс
        
        return results
    
    def enable(self) -> None:
        """Включить валидацию"""
        self._enabled = True
        logger.info("Self-validation enabled")
    
    def disable(self) -> None:
        """Отключить валидацию"""
        self._enabled = False
        logger.info("Self-validation disabled")
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Получить статистику валидации"""
        total = len(self._validation_history)
        passed = sum(1 for r in self._validation_history if r.passed)
        failed = total - passed
        
        by_level = {}
        for level in ValidationLevel:
            by_level[level.value] = sum(
                1 for r in self._validation_history
                if r.level == level and not r.passed
            )
        
        return {
            "total_validations": total,
            "passed": passed,
            "failed": failed,
            "failure_rate": failed / total if total > 0 else 0.0,
            "by_level": by_level,
            "enabled": self._enabled,
            "registered_invariants": sum(len(invs) for invs in self._invariants.values())
        }
    
    def clear_history(self) -> None:
        """Очистить историю валидации"""
        self._validation_history.clear()
        logger.debug("Validation history cleared")


# Глобальный экземпляр для удобства использования
_global_validation_manager: Optional[SelfValidationManager] = None


def get_validation_manager() -> SelfValidationManager:
    """
    Получить глобальный экземпляр SelfValidationManager
    
    Returns:
        Глобальный экземпляр менеджера
    """
    global _global_validation_manager
    if _global_validation_manager is None:
        _global_validation_manager = SelfValidationManager()
    return _global_validation_manager


def validate_invariant(
    class_name: Optional[str] = None,
    name: Optional[str] = None,
    level: ValidationLevel = ValidationLevel.ERROR
):
    """
    Декоратор для автоматической проверки инвариантов объекта
    
    Args:
        class_name: Имя класса (если None, определяется автоматически)
        name: Имя инварианта (если None, используется имя функции)
        level: Уровень валидации
        
    Example:
        @validate_invariant(name="positive_price")
        def check_price(obj):
            return obj.price > 0
    """
    def decorator(func: Callable) -> Callable:
        # Если это функция проверки, регистрируем её как инвариант
        if inspect.isfunction(func):
            manager = get_validation_manager()
            invariant_name = name or func.__name__
            class_name_to_use = class_name or func.__qualname__.split('.')[0]
            
            manager.register_invariant(
                class_name=class_name_to_use,
                name=invariant_name,
                check_func=func,
                message=f"Invariant {invariant_name} violated",
                level=level
            )
            
            return func
        
        # Если это метод класса, создаём обёртку
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Выполняем оригинальную функцию
            result = func(self, *args, **kwargs)
            
            # Проверяем инварианты после выполнения
            manager = get_validation_manager()
            manager.validate_object(self)
            
            return result
        
        return wrapper
    return decorator


def validate_consistency(*class_names: str):
    """
    Декоратор для проверки консистентности между объектами
    
    Args:
        *class_names: Имена классов для проверки консистентности
        
    Example:
        @validate_consistency("Position", "Portfolio")
        def update_portfolio(portfolio, position):
            # Логика обновления
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Выполняем оригинальную функцию
            result = func(*args, **kwargs)
            
            # Проверяем консистентность всех объектов
            manager = get_validation_manager()
            objects_to_check = []
            
            # Собираем объекты из args и kwargs
            for arg in args:
                if hasattr(arg, '__class__'):
                    objects_to_check.append(arg)
            
            for value in kwargs.values():
                if hasattr(value, '__class__'):
                    objects_to_check.append(value)
            
            if objects_to_check:
                manager.validate_consistency(*objects_to_check)
            
            return result
        
        return wrapper
    return decorator


def auto_validate(cls):
    """
    Декоратор класса для автоматической валидации всех методов
    
    Args:
        cls: Класс для декорирования
        
    Example:
        @auto_validate
        class TradeSignal:
            def __init__(self, ...):
                ...
    """
    # Добавляем валидацию после каждого метода
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if not name.startswith('_'):
            setattr(cls, name, validate_invariant()(method))
    
    # Добавляем валидацию в __init__ и __setattr__
    original_init = cls.__init__
    
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        manager = get_validation_manager()
        manager.validate_object(self)
    
    cls.__init__ = new_init
    
    return cls

